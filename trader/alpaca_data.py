"""Alpaca data layer: calendar/clock, pre-market gapper screening, 1-minute
candles (websocket preferred, polling fallback), RVOL, historical bars, and
the inputs MACD needs. Alpaca is authoritative for all analytics/candles.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Callable

from trader.models import Candle

logger = logging.getLogger("trader.alpaca")


class AlpacaDataError(Exception):
    """Raised when the Alpaca feed is unavailable or returns unusable data."""


@dataclass
class ScreenCandidate:
    ticker: str
    price: float
    gap_pct: float
    rvol: float
    volume: float
    float_millions: float | None  # None => unknown float, caller must flag it
    macd_bullish: bool

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "price": round(self.price, 4),
            "gap_pct": round(self.gap_pct, 2),
            "rvol": round(self.rvol, 2),
            "volume": int(self.volume),
            "float_millions": (round(self.float_millions, 1) if self.float_millions is not None else "unknown"),
            "macd_bullish": self.macd_bullish,
        }


class AlpacaData:
    """Wraps alpaca-py's trading + historical/live market-data clients."""

    def __init__(self, api_key: str, api_secret: str, paper: bool = True, feed: str = "iex"):
        from alpaca.data.enums import DataFeed
        from alpaca.data.historical.screener import ScreenerClient
        from alpaca.data.historical.stock import StockHistoricalDataClient
        from alpaca.trading.client import TradingClient

        self.trading_client = TradingClient(api_key, api_secret, paper=paper)
        self.history_client = StockHistoricalDataClient(api_key, api_secret)
        self.screener_client = ScreenerClient(api_key, api_secret)
        self._api_key = api_key
        self._api_secret = api_secret
        # Free/basic Alpaca market-data plans only permit the IEX feed; SIP
        # (the request-level default when `feed` is omitted) 403s with
        # "subscription does not permit querying recent SIP data" for any
        # request touching the last ~15 minutes. Pass `feed="sip"` if the
        # account has a paid SIP subscription.
        self.feed = DataFeed(feed)

    def _resolve_feed(self, start: datetime, end: datetime):
        """IEX is real-time on every plan; SIP is the fuller consolidated tape
        but free/basic plans 403 on any SIP request touching the last ~15
        minutes. Any request whose range reaches into today needs IEX --
        otherwise use whatever feed is configured (IEX by default, or SIP on a
        paid plan for fully historical days)."""
        from alpaca.data.enums import DataFeed

        today = datetime.utcnow().date()
        if start.date() >= today or end.date() >= today:
            return DataFeed.IEX
        return self.feed

    # -- screening ---------------------------------------------------------

    def screen_premarket_gappers(
        self,
        price_min: float,
        price_max: float,
        min_rvol: float,
        macd_fast: int,
        macd_slow: int,
        macd_signal: int,
        macd_mode: str,
        max_candidates: int = 15,
    ) -> list[ScreenCandidate]:
        """Mechanical (non-LLM) pre-market screen.

        Pulls Alpaca's top gainers as the initial universe, then filters to
        price range, RVOL, and MACD-bullish, computing float where Alpaca's
        asset metadata makes it available (otherwise the candidate is kept
        with `float_millions=None` for the caller to flag as unknown).
        """
        from alpaca.data.requests import MarketMoversRequest

        movers = self.screener_client.get_market_movers(
            MarketMoversRequest(market_type="stocks", top=50)
        )
        gainer_symbols = [m.symbol for m in getattr(movers, "gainers", [])]

        candidates: list[ScreenCandidate] = []
        for symbol in gainer_symbols:
            try:
                stat = self._build_candidate_stats(symbol, macd_fast, macd_slow, macd_signal, macd_mode)
            except AlpacaDataError as exc:
                logger.debug("Skipping %s during screen: %s", symbol, exc)
                continue
            if stat is None:
                continue
            if not (price_min <= stat.price <= price_max):
                continue
            if stat.rvol < min_rvol:
                continue
            candidates.append(stat)
            if len(candidates) >= max_candidates:
                break

        candidates.sort(key=lambda c: c.rvol, reverse=True)
        return candidates[:max_candidates]

    def _build_candidate_stats(
        self, symbol: str, macd_fast: int, macd_slow: int, macd_signal: int, macd_mode: str
    ) -> ScreenCandidate | None:
        from trader.indicators import macd_is_bullish, relative_volume

        daily_bars = self.get_daily_bars(symbol, limit=21)
        if len(daily_bars) < 2:
            return None
        prev_close = daily_bars[-2].close
        today_bars = self.get_recent_minute_bars(symbol, limit=max(macd_slow + macd_signal + 5, 40))
        if not today_bars:
            return None
        last = today_bars[-1]

        gap_pct = (last.close - prev_close) / prev_close * 100.0 if prev_close else 0.0

        avg_daily_volume = sum(b.volume for b in daily_bars[:-1]) / max(len(daily_bars) - 1, 1)
        today_volume = sum(b.volume for b in today_bars)
        rvol = relative_volume(today_volume, avg_daily_volume)

        closes = [b.close for b in today_bars]
        bullish = macd_is_bullish(closes, macd_fast, macd_slow, macd_signal, macd_mode)

        float_millions = self._get_float_millions(symbol)

        return ScreenCandidate(
            ticker=symbol,
            price=last.close,
            gap_pct=gap_pct,
            rvol=rvol,
            volume=today_volume,
            float_millions=float_millions,
            macd_bullish=bullish,
        )

    def _get_float_millions(self, symbol: str) -> float | None:
        try:
            asset = self.trading_client.get_asset(symbol)
        except Exception:  # noqa: BLE001 - unknown float must never hard-fail the screen
            return None
        shares = getattr(asset, "shares_outstanding", None) or getattr(asset, "float_shares", None)
        if shares is None:
            return None
        return float(shares) / 1_000_000.0

    # -- bars ---------------------------------------------------------------

    def get_recent_minute_bars(self, symbol: str, limit: int = 60) -> list[Candle]:
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame

        end = datetime.utcnow()
        start = end - timedelta(days=2)  # generous window; we slice to `limit` after
        try:
            request = StockBarsRequest(
                symbol_or_symbols=symbol, timeframe=TimeFrame.Minute, start=start, end=end, limit=limit,
                feed=self._resolve_feed(start, end),
            )
            bar_set = self.history_client.get_stock_bars(request)
        except Exception as exc:  # noqa: BLE001
            raise AlpacaDataError(f"Failed to fetch minute bars for {symbol}: {exc}") from exc

        bars = bar_set.data.get(symbol, []) if hasattr(bar_set, "data") else bar_set.get(symbol, [])
        candles = [_bar_to_candle(b) for b in bars]
        return candles[-limit:]

    def get_daily_bars(self, symbol: str, limit: int = 21) -> list[Candle]:
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame

        end = datetime.utcnow()
        start = end - timedelta(days=int(limit * 1.6) + 5)
        try:
            request = StockBarsRequest(
                symbol_or_symbols=symbol, timeframe=TimeFrame.Day, start=start, end=end, limit=limit,
                feed=self._resolve_feed(start, end),
            )
            bar_set = self.history_client.get_stock_bars(request)
        except Exception as exc:  # noqa: BLE001
            raise AlpacaDataError(f"Failed to fetch daily bars for {symbol}: {exc}") from exc

        bars = bar_set.data.get(symbol, []) if hasattr(bar_set, "data") else bar_set.get(symbol, [])
        return [_bar_to_candle(b) for b in bars][-limit:]

    def get_avg_daily_volume(self, symbol: str, lookback_days: int = 30) -> float | None:
        """Trailing average daily volume, excluding today (today's volume is
        partial and would understate/overstate a same-day RVOL baseline).
        Used as the RVOL gate's baseline; `None` if no daily bars are available."""
        daily_bars = self.get_daily_bars(symbol, limit=lookback_days + 1)
        history_bars = [b for b in daily_bars if b.timestamp.date() < datetime.utcnow().date()]
        if not history_bars:
            return None
        return sum(b.volume for b in history_bars) / len(history_bars)

    def get_minute_bars_for_day(self, symbol: str, day: object) -> list[Candle]:
        """Full day of 1-minute bars for `day` (a `datetime.date`) -- used by
        scripts/record_bars.py to build --replay fixtures."""
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame

        start = datetime(day.year, day.month, day.day)
        end = start + timedelta(days=1)
        try:
            request = StockBarsRequest(
                symbol_or_symbols=symbol, timeframe=TimeFrame.Minute, start=start, end=end, limit=1000,
                feed=self._resolve_feed(start, end),
            )
            bar_set = self.history_client.get_stock_bars(request)
        except Exception as exc:  # noqa: BLE001
            raise AlpacaDataError(f"Failed to fetch day bars for {symbol} on {day}: {exc}") from exc

        bars = bar_set.data.get(symbol, []) if hasattr(bar_set, "data") else bar_set.get(symbol, [])
        return [_bar_to_candle(b) for b in bars]

    def validate_ticker(self, symbol: str) -> bool:
        try:
            asset = self.trading_client.get_asset(symbol)
        except Exception:  # noqa: BLE001
            return False
        return bool(getattr(asset, "tradable", False))

    def get_account_equity_check(self) -> None:
        """Cheap connectivity probe used by --selftest."""
        try:
            self.trading_client.get_clock()
        except Exception as exc:  # noqa: BLE001
            raise AlpacaDataError(f"Alpaca connectivity check failed: {exc}") from exc


def _bar_to_candle(bar: object) -> Candle:
    return Candle(
        timestamp=getattr(bar, "timestamp"),
        open=float(getattr(bar, "open")),
        high=float(getattr(bar, "high")),
        low=float(getattr(bar, "low")),
        close=float(getattr(bar, "close")),
        volume=float(getattr(bar, "volume")),
    )


class AlpacaBarStream:
    """1-minute bar subscription: websocket preferred, polling fallback.

    Calls `on_bar(symbol, Candle)` for every completed 1-minute bar. If the
    websocket connection drops or fails to establish, falls back to polling
    Alpaca's REST bars endpoint once per minute for the same symbols.
    """

    def __init__(self, api_key: str, api_secret: str, data: AlpacaData, symbols: list[str]):
        self._api_key = api_key
        self._api_secret = api_secret
        self._data = data
        self.symbols = list(symbols)
        self._on_bar: Callable[[str, Candle], None] | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.mode: str = "unstarted"  # "websocket" | "polling"
        self._seen_timestamps: dict[str, datetime] = {}

    def start(self, on_bar: Callable[[str, Candle], None]) -> None:
        self._on_bar = on_bar
        try:
            self._start_websocket()
            self.mode = "websocket"
        except Exception as exc:  # noqa: BLE001
            logger.warning("Websocket bar stream failed (%s); falling back to polling", exc)
            self._start_polling()
            self.mode = "polling"

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)

    def _start_websocket(self) -> None:
        from alpaca.data.enums import DataFeed
        from alpaca.data.live.stock import StockDataStream

        # The live bar stream is always "today, right now" -- always use IEX
        # (real-time on every plan) regardless of the configured feed, which
        # may be SIP for historical requests elsewhere.
        stream = StockDataStream(self._api_key, self._api_secret, feed=DataFeed.IEX)

        async def _handler(bar: object) -> None:
            candle = _bar_to_candle(bar)
            symbol = getattr(bar, "symbol")
            if self._on_bar:
                self._on_bar(symbol, candle)

        stream.subscribe_bars(_handler, *self.symbols)

        def _run() -> None:
            try:
                stream.run()
            except Exception as exc:  # noqa: BLE001
                if not self._stop.is_set():
                    logger.warning("Websocket bar stream crashed (%s); switching to polling", exc)
                    self._start_polling()
                    self.mode = "polling"

        self._thread = threading.Thread(target=_run, daemon=True, name="alpaca-ws")
        self._thread.start()
        time.sleep(1.0)  # give the connection a moment to fail fast if it's going to

    def _start_polling(self) -> None:
        def _poll_loop() -> None:
            while not self._stop.is_set():
                for symbol in self.symbols:
                    try:
                        bars = self._data.get_recent_minute_bars(symbol, limit=2)
                    except AlpacaDataError as exc:
                        logger.warning("Polling fetch failed for %s: %s", symbol, exc)
                        continue
                    if not bars:
                        continue
                    latest = bars[-1]
                    if self._seen_timestamps.get(symbol) != latest.timestamp:
                        self._seen_timestamps[symbol] = latest.timestamp
                        if self._on_bar:
                            self._on_bar(symbol, latest)
                self._stop.wait(15)

        self._thread = threading.Thread(target=_poll_loop, daemon=True, name="alpaca-poll")
        self._thread.start()
