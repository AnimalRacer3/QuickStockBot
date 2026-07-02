"""Daily lifecycle orchestration: startup, calendar check, 9:15 selection,
9:30 re-validation/freeze, the 1-minute monitoring loop, and shutdown.

The per-candle decision logic (`on_new_candle` / `manage_position_exit`) is
shared between the live engine and `--replay` so pattern/risk behavior is
identical in both, and only the data/execution sources differ.

Exit codes: 0 clean day/closed market, 2 kill-switch, 3 config/auth error, 4 data-feed failure.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Protocol

from trader import indicators, patterns, risk
from trader.config import Config
from trader.journal import Journal, TradeRecord
from trader.market_calendar import SessionInfo
from trader.models import Candle, ExitReason, Position, WatchlistEntry

logger = logging.getLogger("trader.engine")

EXIT_OK = 0
EXIT_KILL_SWITCH = 2
EXIT_CONFIG_ERROR = 3
EXIT_DATA_FEED_ERROR = 4


class ExecutionLike(Protocol):
    def enter_long(self, ticker: str, qty: int) -> object: ...
    def exit_long(self, ticker: str, qty: int) -> object: ...


@dataclass
class DayState:
    starting_equity: float
    buying_power: float
    equity: float
    green_peak_equity: float
    market_open: datetime
    market_close: datetime
    z_hour_cutoff_time: datetime
    force_close_time: datetime
    no_trade_cutoff_time: datetime
    frozen_watchlist: set[str] = field(default_factory=set)
    positions: dict[str, Position] = field(default_factory=dict)
    candle_history: dict[str, list[Candle]] = field(default_factory=dict)
    vwap_history: dict[str, list[float]] = field(default_factory=dict)
    high_of_day: dict[str, float] = field(default_factory=dict)
    entries_made: int = 0
    kill_switch_hit: bool = False
    giveback_lockout: bool = False
    no_trade_cutoff_hit: bool = False
    data_feed_ok: bool = True
    shutdown_reason: str | None = None


def build_day_state(config: Config, session: SessionInfo, starting_equity: float, buying_power: float) -> DayState:
    return DayState(
        starting_equity=starting_equity,
        buying_power=buying_power,
        equity=starting_equity,
        green_peak_equity=starting_equity,
        market_open=session.market_open,
        market_close=session.market_close,
        z_hour_cutoff_time=session.z_hour_cutoff_time(config.z_hour_cutoff),
        force_close_time=session.force_close_time(config.force_close_offset_min),
        no_trade_cutoff_time=session.no_trade_cutoff_time(config.no_trade_cutoff_hours),
    )


def freeze_watchlist(state: DayState, entries: list[WatchlistEntry]) -> None:
    state.frozen_watchlist = {e.ticker for e in entries}
    for ticker in state.frozen_watchlist:
        state.candle_history.setdefault(ticker, [])
        state.vwap_history.setdefault(ticker, [])


def _pattern_enabled_map(config: Config) -> dict[str, bool]:
    p = config.patterns
    return {
        "morning_star": p.morning_star,
        "three_white_soldiers": p.three_white_soldiers,
        "rising_three_methods": p.rising_three_methods,
        "pullback": p.pullback,
        "breakout_base": p.breakout_base,
    }


def on_new_candle(
    ticker: str,
    candle: Candle,
    now: datetime,
    state: DayState,
    config: Config,
    execution: ExecutionLike,
    journal: Journal,
) -> None:
    """Process one completed 1-minute candle for one ticker: manage an
    existing position's exits, or evaluate a fresh entry."""
    history = state.candle_history.setdefault(ticker, [])
    history.append(candle)
    vwap_values = state.vwap_history.setdefault(ticker, [])
    vwap_values.append(indicators.vwap(history))
    state.high_of_day[ticker] = max(state.high_of_day.get(ticker, candle.high), candle.high)

    if ticker in state.positions:
        manage_position_exit(ticker, candle, vwap_values[-1], history, state, config, execution, journal, now)
        return

    if ticker not in state.frozen_watchlist:
        return
    if state.kill_switch_hit or state.no_trade_cutoff_hit:
        return
    if len(state.positions) >= config.max_positions:
        journal.record_skip(ticker, "max_positions_reached")
        return
    if now >= state.z_hour_cutoff_time:
        journal.record_skip(ticker, "past_z_hour_cutoff")
        return
    if state.giveback_lockout:
        journal.record_skip(ticker, "profit_giveback_lockout")
        return

    matches = patterns.detect_all(
        history,
        enabled=_pattern_enabled_map(config),
        vwap_values=vwap_values,
        high_of_day=state.high_of_day[ticker],
    )
    if not matches:
        return
    match = matches[0]

    price = candle.close
    pct_above_vwap = indicators.pct_above_vwap(price, vwap_values[-1])
    if pct_above_vwap < 0:
        journal.record_skip(ticker, "below_vwap", details=f"pct={pct_above_vwap:.2f}")
        return
    if pct_above_vwap > config.overextension_pct:
        journal.record_skip(ticker, "overextended", details=f"pct={pct_above_vwap:.2f}")
        return
    if not indicators.macd_is_bullish(
        [c.close for c in history], config.macd.fast, config.macd.slow, config.macd.signal, config.macd.mode
    ):
        journal.record_skip(ticker, "macd_not_bullish")
        return
    prior_5 = history[-6:-1]
    if not prior_5 or not indicators.volume_confirmed(candle, prior_5):
        journal.record_skip(ticker, "no_volume_confirmation")
        return

    qty = risk.position_size(
        state.equity, state.buying_power, price, config.risk_per_trade_pct, config.stop_loss_pct, config.max_position_pct_bp
    )
    if qty <= 0:
        journal.record_skip(ticker, "position_size_zero")
        return

    fill = execution.enter_long(ticker, qty)
    stop = risk.stop_price(fill.fill_price, config.stop_loss_pct)
    target = risk.target_price(fill.fill_price, config.take_profit_pct)
    position = Position(
        ticker=ticker,
        qty=qty,
        entry_price=fill.fill_price,
        entry_time=now,
        stop_price=stop,
        target_price=target,
        pattern=match.pattern,
        pattern_candle_timestamps=match.candle_timestamps,
    )
    state.positions[ticker] = position
    state.entries_made += 1
    logger.info("ENTER %s qty=%s @ %.4f pattern=%s", ticker, qty, fill.fill_price, match.pattern)


def manage_position_exit(
    ticker: str,
    candle: Candle,
    vwap_value: float,
    history: list[Candle],
    state: DayState,
    config: Config,
    execution: ExecutionLike,
    journal: Journal,
    now: datetime,
    forced_reason: ExitReason | None = None,
) -> None:
    position = state.positions[ticker]
    position.peak_price = max(position.peak_price, candle.high)

    if forced_reason is not None:
        reason, scale_pct = forced_reason, 100.0
    else:
        prior_5 = history[-6:-1]
        vol_confirmed = bool(prior_5) and indicators.volume_confirmed(candle, prior_5)
        risk_cfg = risk.RiskConfig(
            stop_loss_pct=config.stop_loss_pct,
            take_profit_pct=config.take_profit_pct,
            trail_off_trigger_pct=config.trail_off_trigger_pct,
            trail_off_scale_out_pct=config.trail_off_scale_out_pct,
            overextension_pct=config.overextension_pct,
        )
        reason, scale_pct = risk.evaluate_exit(position, candle, vwap_value, vol_confirmed, risk_cfg)

    if reason is None:
        return

    qty_to_sell = position.remaining_qty if reason != ExitReason.TRAIL_OFF else position.remaining_qty * (scale_pct / 100.0)
    qty_to_sell = round(qty_to_sell)
    if qty_to_sell <= 0:
        return

    fill = execution.exit_long(ticker, qty_to_sell)
    pnl_dollars = (fill.fill_price - position.entry_price) * qty_to_sell
    pnl_pct = (fill.fill_price - position.entry_price) / position.entry_price * 100.0
    state.equity += pnl_dollars
    state.green_peak_equity = max(state.green_peak_equity, state.equity)

    is_full_exit = reason != ExitReason.TRAIL_OFF
    if reason == ExitReason.TRAIL_OFF:
        position.scaled_out_pct = risk.next_scale_out_pct(position.scaled_out_pct, config.trail_off_scale_out_pct)
        if position.scaled_out_pct >= 100.0:
            is_full_exit = True

    journal.record_trade(
        TradeRecord(
            time=position.entry_time.isoformat(),
            ticker=ticker,
            side="buy",
            qty=qty_to_sell,
            fill_price=position.entry_price,
            pattern=position.pattern,
            pattern_candle_timestamps=position.pattern_candle_timestamps,
            stop=position.stop_price,
            target=position.target_price,
            exit_price=fill.fill_price,
            exit_time=now.isoformat(),
            exit_reason=reason.value,
            pnl_dollars=pnl_dollars,
            pnl_pct=pnl_pct,
            simulated=fill.simulated,
        )
    )
    logger.info(
        "EXIT %s qty=%s @ %.4f reason=%s pnl=%.2f (%.2f%%)",
        ticker, qty_to_sell, fill.fill_price, reason.value, pnl_dollars, pnl_pct,
    )

    if is_full_exit:
        del state.positions[ticker]


def flatten_all(state: DayState, reason: ExitReason, config: Config, execution: ExecutionLike, journal: Journal, now: datetime) -> None:
    for ticker in list(state.positions.keys()):
        history = state.candle_history.get(ticker, [])
        if not history:
            continue
        last_candle = history[-1]
        vwap_value = state.vwap_history[ticker][-1] if state.vwap_history.get(ticker) else last_candle.close
        manage_position_exit(ticker, last_candle, vwap_value, history, state, config, execution, journal, now, forced_reason=reason)


def check_terminal_trigger(state: DayState, now: datetime, config: Config) -> str | None:
    """Checks the triggers that end the trading day. Giveback is handled
    separately (`check_giveback`) since it only blocks new entries, not the loop."""
    if risk.kill_switch_triggered(state.starting_equity, state.equity, config.daily_kill_switch_pct):
        return "kill_switch"
    if now >= state.force_close_time:
        return "force_close"
    if not state.no_trade_cutoff_hit and risk.no_trade_cutoff_triggered(
        now, state.market_open, config.no_trade_cutoff_hours, state.entries_made
    ):
        return "no_trade_cutoff"
    return None


def check_giveback(state: DayState, config: Config) -> bool:
    """Sets (and returns) the giveback lockout flag once triggered. Non-terminal:
    blocks new entries but lets the day continue managing existing exits."""
    if not state.giveback_lockout and risk.profit_giveback_triggered(
        state.starting_equity, state.green_peak_equity, state.equity, config.daily_profit_giveback_pct
    ):
        state.giveback_lockout = True
        logger.info("Profit-giveback threshold hit: no new entries, managing exits only.")
    return state.giveback_lockout


def run_live_day(config: Config, secrets, run_date: date | None = None) -> int:
    """Full daily lifecycle against live Alpaca + Robinhood MCP. Returns an exit code."""
    import queue
    import time as time_module

    from trader.alpaca_data import AlpacaBarStream, AlpacaData, AlpacaDataError
    from trader.anthropic_select import run_ticker_selection
    from trader.execution import ExecutionEngine
    from trader.lock import AlreadyRunningError, InstanceLock
    from trader.logging_setup import setup_logging
    from trader.market_calendar import MarketCalendar
    from trader.mcp_robinhood import MCPConfigError, RobinhoodMCPClient, discover_robinhood_mcp_server
    from trader.reporting import DailyReportInputs, build_report, save_report

    run_date = run_date or date.today()
    config.paths.ensure()
    setup_logging(config.paths.logs_dir, run_date.isoformat())
    journal = Journal(config.paths, run_date)

    lock = InstanceLock(config.paths.base_dir / "trader.lock")
    try:
        lock.acquire()
    except AlreadyRunningError as exc:
        logger.error(str(exc))
        return EXIT_CONFIG_ERROR

    try:
        try:
            alpaca = AlpacaData(secrets.alpaca_key, secrets.alpaca_secret, paper=not config.is_live, feed=config.alpaca_data_feed)
            alpaca.get_account_equity_check()
        except AlpacaDataError as exc:
            logger.error("Alpaca connection failed at startup: %s", exc)
            return EXIT_DATA_FEED_ERROR

        calendar = MarketCalendar(alpaca.trading_client, config.timezone)
        session = calendar.get_session_info(run_date)
        if not session.is_open:
            logger.info("Market closed on %s.", run_date)
            report = build_report(
                DailyReportInputs(
                    run_date=run_date, mode=config.mode, starting_equity=0.0, ending_equity=0.0,
                    watchlist=[], claude_cost_usd=0.0, claude_notes="",
                    zero_trade_day=True, zero_trade_reason="Market closed (holiday or weekend).",
                ),
                journal,
            )
            save_report(config.paths.reports_dir, run_date, report)
            return EXIT_OK

        try:
            mcp_spec = discover_robinhood_mcp_server()
            mcp = RobinhoodMCPClient(mcp_spec)
            mcp.connect()
        except MCPConfigError as exc:
            logger.error("Robinhood MCP connection/auth failed; halting all trading: %s", exc)
            return EXIT_CONFIG_ERROR

        try:
            account = mcp.get_account()
            starting_equity = float(account.get("equity") or account.get("portfolio_value"))
            buying_power = float(account.get("buying_power"))
        except (KeyError, TypeError, ValueError) as exc:
            logger.error("Could not parse account snapshot from Robinhood MCP: %s", exc)
            return EXIT_CONFIG_ERROR

        state = build_day_state(config, session, starting_equity, buying_power)
        execution = ExecutionEngine(config.mode, mcp)

        candidates = alpaca.screen_premarket_gappers(
            config.price_min, config.price_max, config.min_rvol,
            config.macd.fast, config.macd.slow, config.macd.signal, config.macd.mode,
            config.anthropic.max_candidates,
        )
        selection = run_ticker_selection(
            secrets.anthropic_api_key, config.anthropic.model, config.anthropic.max_tokens,
            config.watchlist_size, candidates, alpaca,
            config.paths.logs_dir / f"{run_date.isoformat()}-claude.log",
        )

        if selection.no_trade_day or not selection.watchlist:
            report = build_report(
                DailyReportInputs(
                    run_date=run_date, mode=config.mode, starting_equity=starting_equity, ending_equity=starting_equity,
                    watchlist=[], claude_cost_usd=selection.cost_usd, claude_notes=selection.notes,
                    zero_trade_day=True, zero_trade_reason="No qualifying tickers from the 9:15 selection.",
                    screen_summary="\n".join(str(c.to_dict()) for c in candidates),
                ),
                journal,
            )
            save_report(config.paths.reports_dir, run_date, report)
            journal.append_run_summary(config.mode, "no_trade_day", selection.cost_usd, 0.0)
            return EXIT_OK

        now = datetime.now(session.market_open.tzinfo)
        if now < session.market_open:
            time_module.sleep(max(0.0, (session.market_open - now).total_seconds()))

        survivors = _revalidate_at_open(alpaca, selection.watchlist, config)
        if not survivors:
            report = build_report(
                DailyReportInputs(
                    run_date=run_date, mode=config.mode, starting_equity=starting_equity, ending_equity=starting_equity,
                    watchlist=selection.watchlist, claude_cost_usd=selection.cost_usd, claude_notes=selection.notes,
                    zero_trade_day=True, zero_trade_reason="No watchlist tickers survived the 9:30 re-validation.",
                ),
                journal,
            )
            save_report(config.paths.reports_dir, run_date, report)
            journal.append_run_summary(config.mode, "no_trade_day", selection.cost_usd, 0.0)
            return EXIT_OK

        freeze_watchlist(state, survivors)

        if config.is_live:
            _print_live_warning_banner(config, starting_equity)

        bar_queue: "queue.Queue[tuple[str, Candle]]" = queue.Queue()
        stream = AlpacaBarStream(secrets.alpaca_key, secrets.alpaca_secret, alpaca, list(state.frozen_watchlist))
        stream.start(on_bar=lambda symbol, candle: bar_queue.put((symbol, candle)))

        result = "normal_close"
        exit_code = EXIT_OK
        try:
            while True:
                try:
                    symbol, candle = bar_queue.get(timeout=5.0)
                    now = candle.timestamp
                    on_new_candle(symbol, candle, now, state, config, execution, journal)
                except queue.Empty:
                    now = datetime.now(session.market_open.tzinfo)

                check_giveback(state, config)
                trigger = check_terminal_trigger(state, now, config)
                if trigger == "kill_switch":
                    state.kill_switch_hit = True
                    flatten_all(state, ExitReason.KILL_SWITCH, config, execution, journal, now)
                    result, exit_code = "kill_switch", EXIT_KILL_SWITCH
                    break
                if trigger == "force_close":
                    flatten_all(state, ExitReason.FORCE_CLOSE, config, execution, journal, now)
                    result, exit_code = "normal_close", EXIT_OK
                    break
                if trigger == "no_trade_cutoff":
                    state.no_trade_cutoff_hit = True
                    result, exit_code = "no_trade_cutoff", EXIT_OK
                    break
        finally:
            stream.stop()

        report = build_report(
            DailyReportInputs(
                run_date=run_date, mode=config.mode, starting_equity=starting_equity, ending_equity=state.equity,
                watchlist=selection.watchlist, claude_cost_usd=selection.cost_usd, claude_notes=selection.notes,
                zero_trade_day=False,
            ),
            journal,
        )
        save_report(config.paths.reports_dir, run_date, report)
        journal.append_run_summary(config.mode, result, selection.cost_usd, state.equity - starting_equity)
        return exit_code
    finally:
        lock.release()


def _revalidate_at_open(alpaca, entries: list[WatchlistEntry], config: Config) -> list[WatchlistEntry]:
    """9:30 re-check: still in price range, above/near VWAP, RVOL holding. Ranked survivors, capped at watchlist_size."""
    survivors: list[WatchlistEntry] = []
    for entry in entries:
        bars = alpaca.get_recent_minute_bars(entry.ticker, limit=30)
        if not bars:
            continue
        last = bars[-1]
        if not (config.price_min <= last.close <= config.price_max):
            continue
        vwap_value = indicators.vwap(bars)
        if indicators.pct_above_vwap(last.close, vwap_value) < -1.0:  # allow "basing near it"
            continue
        survivors.append(entry)
    return survivors[: config.watchlist_size]


def _print_live_warning_banner(config: Config, starting_equity: float) -> None:
    import time as time_module

    kill_switch_dollars = starting_equity * abs(config.daily_kill_switch_pct) / 100.0
    print("=" * 70)
    print("  LIVE TRADING MODE -- REAL ORDERS WILL BE PLACED")
    print(
        f"  Daily kill-switch: {config.daily_kill_switch_pct}% of starting equity "
        f"(${kill_switch_dollars:,.2f})"
    )
    print("  Ctrl+C now to abort before the first order is placed.")
    print("=" * 70)
    time_module.sleep(10)
