"""Momentum scanner orchestrator (Section 5)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Callable, Optional

from bot.alpaca.client import MarketClient
from bot.news.models import TickerSentiment
from bot.scanner.config import ScannerConfig
from bot.scanner.filters import (
    compute_gap_pct,
    compute_rvol,
    passes_float_filter,
    passes_gap_up_filter,
    passes_news_filter,
    passes_price_filter,
    passes_rvol_filter,
)
from bot.scanner.fundamentals import get_float_shares
from bot.scanner.leaders import assign_roles
from bot.scanner.models import ScanResult, ScanWindow, TickerState
from bot.scanner.window import get_scan_window, is_in_window
from bot.ta.config import TAConfig
from bot.ta.macd import classify_macd
from bot.ta.models import MacdState
from bot.ta.patterns import run_enabled_patterns
from bot.ta.scoring import compute_score
from bot.ta.similarity import pattern_signature

logger = logging.getLogger(__name__)

# Sentinel MACD state used when there are not enough bars to compute MACD.
_NULL_MACD = MacdState(value=0.0, slope=0.0, hist=0.0, favorability=0.0, eligible=False)

# Approximate regular-session length in hours (used for RVOL denominator)
_SESSION_HOURS = 6.5

# Type alias for the prior-profit lookup callback (symbol → net P/L or None)
PriorProfitLookup = Callable[[str], Optional[float]]


def _null_prior_profit(symbol: str) -> Optional[float]:  # noqa: ARG001
    return None


def _session_elapsed_fraction(now: datetime, session_open: datetime) -> float:
    """Fraction of the regular session elapsed at *now* (0..1, capped at 1)."""
    elapsed_h = (now - session_open).total_seconds() / 3600.0
    if elapsed_h <= 0:
        return 0.0
    return min(1.0, elapsed_h / _SESSION_HOURS)


def scan_candidates(
    symbols: list[str],
    client: MarketClient,
    config: ScannerConfig,
    ta_config: TAConfig,
    window: ScanWindow,
    news_by_symbol: dict[str, TickerSentiment],
    prior_profit: PriorProfitLookup = _null_prior_profit,
    finnhub_api_key: Optional[str] = None,
    now: Optional[datetime] = None,
) -> list[TickerState]:
    """Build TickerState for every candidate symbol.

    Steps per symbol:
    1. Fetch intraday bars → price, cumulative volume, MACD, patterns, signature.
    2. Fetch previous-close bar → gap %.
    3. Fundamentals → float shares.
    4. Compute RVOL.
    5. Apply filters.
    6. Compute score (TA scoring + prior-profit bias).
    7. Build TickerState.
    """
    if now is None:
        now = datetime.now(tz=timezone.utc)

    elapsed_frac = _session_elapsed_fraction(now, window.session_open)
    states: list[TickerState] = []

    for symbol in symbols:
        try:
            state = _evaluate_symbol(
                symbol=symbol,
                client=client,
                config=config,
                ta_config=ta_config,
                window=window,
                elapsed_frac=elapsed_frac,
                news_by_symbol=news_by_symbol,
                prior_profit=prior_profit,
                finnhub_api_key=finnhub_api_key,
                now=now,
            )
            if state is not None:
                states.append(state)
        except Exception:
            logger.exception("Error evaluating %s", symbol)

    return states


def _evaluate_symbol(
    *,
    symbol: str,
    client: MarketClient,
    config: ScannerConfig,
    ta_config: TAConfig,
    window: ScanWindow,
    elapsed_frac: float,
    news_by_symbol: dict[str, TickerSentiment],
    prior_profit: PriorProfitLookup,
    finnhub_api_key: Optional[str],
    now: datetime,
) -> Optional[TickerState]:
    # Fetch today's intraday bars (1-min)
    bars = client.get_bars(
        symbol=symbol,
        start=window.window_start,
        end=now,
        timeframe="1Min",
        limit=1000,
    )
    if not bars:
        return None

    latest = bars[-1]
    price = float(latest.close)
    today_volume = sum(b.volume for b in bars)

    # Price filter (fast exit)
    if not passes_price_filter(price, config.min_price, config.max_price):
        return None

    # Previous close: fetch last bar from prior session for gap computation.
    # Use a short window the day before window_start.
    prev_close = _get_prev_close(symbol, client, window)
    gap_pct = compute_gap_pct(price, prev_close)
    pct_change = gap_pct  # same definition; keep separate field for clarity

    if not passes_gap_up_filter(price, prev_close, config.gap_up_min_pct):
        return None

    # Float / fundamentals
    float_shares = get_float_shares(symbol, api_key=finnhub_api_key)
    unknown_float = float_shares is None

    if not passes_float_filter(float_shares, unknown_float, config.max_float_shares):
        return None

    # News
    ticker_sentiment = news_by_symbol.get(symbol)
    has_news = _has_positive_news(ticker_sentiment)

    if not passes_news_filter(has_news, config.require_news):
        return None

    # Avg daily volume from bars (trailing proxy: mean daily volume using today's bars
    # extrapolated to a full day; this is an approximation for pre-market when we
    # have limited history — a proper implementation would query historical daily bars)
    avg_daily_vol = _estimate_avg_daily_volume(bars, elapsed_frac)
    rvol = compute_rvol(today_volume, avg_daily_vol, elapsed_frac)

    if not passes_rvol_filter(rvol, config.relative_volume_min):
        return None

    # MACD & patterns
    macd_state = _compute_macd(bars, ta_config)
    pattern_matches = run_enabled_patterns(
        bars,
        ta_config.enabled_patterns,
        ta_config.pattern_candle_lookback,
    )
    sig = pattern_signature(bars[-ta_config.pattern_candle_lookback :])

    # Score
    sentiment_val = _sentiment_score(ticker_sentiment)
    high = max(float(b.high) for b in bars)
    low = min(float(b.low) for b in bars)
    base_score, _ = compute_score(
        symbol=symbol,
        has_news=has_news,
        sentiment_score=sentiment_val,
        macd_state=macd_state,
        pattern_matches=pattern_matches,
        price=price,
        high=high,
        low=low,
    )

    # Prior-profit bias
    prior_pnl = prior_profit(symbol)
    if prior_pnl is not None and prior_pnl > 0:
        bias = prior_pnl * config.prior_profit_bias_weight
        score = min(100.0, base_score + bias)
    else:
        score = base_score

    pattern_tags = [m.tag for m in pattern_matches if m.matched]

    # Tradability: unknown-float tickers are shown always; tradable flag depends on config
    tradable = not (unknown_float and not config.include_unknown_float)

    return TickerState(
        symbol=symbol,
        price=price,
        prev_close=prev_close,
        gap_pct=gap_pct,
        pct_change=pct_change,
        rvol=rvol,
        float_shares=float_shares,
        unknown_float=unknown_float,
        tradable=tradable,
        has_news=has_news,
        macd_state=macd_state,
        pattern_tags=pattern_tags,
        pattern_signature=sig,
        role="standalone",
        score=score,
    )


def _get_prev_close(symbol: str, client: MarketClient, window: ScanWindow) -> float:
    """Fetch the previous session's closing price."""
    from datetime import timedelta

    end = window.window_start
    start = end - timedelta(days=5)  # go back a few days to cover weekends/holidays
    bars = client.get_bars(symbol=symbol, start=start, end=end, timeframe="1Day", limit=5)
    if bars:
        return float(bars[-1].close)
    return 0.0


def _estimate_avg_daily_volume(bars: list, elapsed_frac: float) -> float:
    """Extrapolate today's partial volume to a full-day estimate.

    This is a rough intraday approximation; a production system would use
    historical daily bars.  We use it only as the denominator for RVOL.
    """
    today_volume = sum(b.volume for b in bars)
    if elapsed_frac < 1e-10:
        return float(today_volume)
    return today_volume / elapsed_frac


def _compute_macd(bars: list, ta_config: TAConfig) -> MacdState:
    try:
        return classify_macd(bars, ta_config)
    except Exception:
        return _NULL_MACD


def _has_positive_news(ts: Optional[TickerSentiment]) -> bool:
    if ts is None or not ts.articles:
        return False
    # Positive if the aggregate sentiment score is net positive
    return ts.aggregate.score > 0


def _sentiment_score(ts: Optional[TickerSentiment]) -> float:
    if ts is None:
        return 0.0
    return ts.aggregate.score


def build_active_set(
    candidates: list[TickerState],
    config: ScannerConfig,
    movers: Optional[list[str]] = None,
) -> list[str]:
    """Select the top-N active tickers from candidates.

    Ranking: tradable candidates sorted descending by pct_change.
    Whitelist symbols are appended on top (not consuming a slot).
    If Alpaca movers are provided, intersect tradable candidates with movers
    first (by restricting to symbols present in movers list) when non-empty.

    Unknown-float tickers with tradable=False are visible in candidates
    but do not consume a top-N slot.
    """
    tradable = [c for c in candidates if c.tradable]

    if movers:
        mover_set = set(movers)
        intersected = [c for c in tradable if c.symbol in mover_set]
        if intersected:
            tradable = intersected

    ranked = sorted(tradable, key=lambda s: s.pct_change, reverse=True)
    top = [s.symbol for s in ranked[: config.active_tickers_n]]

    # Whitelist additions (always active, on top)
    for sym in config.whitelist_symbols:
        if sym not in top:
            top.append(sym)

    return top


def run_scan(
    symbols: list[str],
    client: MarketClient,
    config: ScannerConfig,
    ta_config: TAConfig,
    news_by_symbol: dict[str, TickerSentiment],
    prior_profit: PriorProfitLookup = _null_prior_profit,
    finnhub_api_key: Optional[str] = None,
    movers: Optional[list[str]] = None,
    now: Optional[datetime] = None,
) -> Optional[ScanResult]:
    """Full scan pass: window check → filters → leader detection → active set.

    Returns None when outside the scan window (no new tickers added).
    """
    if now is None:
        now = datetime.now(tz=timezone.utc)

    window = get_scan_window(
        client=client,
        pre_open_lead_hours=config.pre_open_lead_hours,
        scan_duration_hours=config.scan_duration_hours,
    )

    if not is_in_window(now, window):
        logger.info("Outside scan window (%s – %s)", window.window_start, window.window_end)
        return None

    candidates = scan_candidates(
        symbols=symbols,
        client=client,
        config=config,
        ta_config=ta_config,
        window=window,
        news_by_symbol=news_by_symbol,
        prior_profit=prior_profit,
        finnhub_api_key=finnhub_api_key,
        now=now,
    )

    # Leader/laggard detection on survivors
    candidates = assign_roles(candidates, config.leader_similarity_threshold)

    active_set = build_active_set(candidates, config, movers=movers)

    logger.info(
        "Scan complete: %d candidates, %d active (%s)",
        len(candidates),
        len(active_set),
        ", ".join(active_set),
    )

    return ScanResult(
        window=window,
        candidates=candidates,
        active_set=active_set,
        scanned_at=now,
    )
