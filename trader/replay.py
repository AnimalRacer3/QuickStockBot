"""`--replay <date>` mode: run the full engine against recorded 1-minute bars
for a past day, skipping the Claude call and using a saved watchlist, so
patterns/risk logic can be validated without waiting for market hours.

Expected files under `config.paths.replay_dir`:
  <date>-watchlist.json   -- [{"ticker","reason","catalyst","rank"}, ...]
  <date>-<TICKER>.json    -- [{"timestamp","open","high","low","close","volume"}, ...]

`scripts/record_bars.py` produces both from live Alpaca data for a given day.
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime
from zoneinfo import ZoneInfo

from trader.config import Config
from trader.engine import (
    EXIT_KILL_SWITCH,
    EXIT_OK,
    build_day_state,
    check_giveback,
    check_terminal_trigger,
    flatten_all,
    freeze_watchlist,
    on_new_candle,
)
from trader.execution import ReplayExecutionEngine
from trader.journal import Journal
from trader.logging_setup import setup_logging
from trader.market_calendar import build_session_info
from trader.models import Candle, ExitReason, WatchlistEntry
from trader.reporting import DailyReportInputs, build_report, save_report

logger = logging.getLogger("trader.replay")

SYNTHETIC_STARTING_EQUITY = 100_000.0


class ReplayError(Exception):
    pass


def _load_watchlist(replay_dir, replay_date: date) -> list[WatchlistEntry]:
    path = replay_dir / f"{replay_date.isoformat()}-watchlist.json"
    if not path.exists():
        raise ReplayError(f"No saved watchlist found for replay: {path}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [WatchlistEntry(ticker=r["ticker"], reason=r["reason"], catalyst=r["catalyst"], rank=r["rank"]) for r in raw]


def _load_bars(replay_dir, replay_date: date, ticker: str, tz: ZoneInfo) -> list[Candle]:
    path = replay_dir / f"{replay_date.isoformat()}-{ticker}.json"
    if not path.exists():
        logger.warning("No recorded bars for %s on %s; skipping in replay.", ticker, replay_date)
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    candles = []
    for r in raw:
        ts = datetime.fromisoformat(r["timestamp"])
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=tz)
        candles.append(Candle(timestamp=ts, open=r["open"], high=r["high"], low=r["low"], close=r["close"], volume=r["volume"]))
    candles.sort(key=lambda c: c.timestamp)
    return candles


def run_replay(config: Config, replay_date: date) -> int:
    config.paths.ensure()
    setup_logging(config.paths.logs_dir, f"replay-{replay_date.isoformat()}")
    journal = Journal(config.paths, replay_date)
    tz = ZoneInfo(config.timezone)

    watchlist = _load_watchlist(config.paths.replay_dir, replay_date)
    bars_by_ticker = {e.ticker: _load_bars(config.paths.replay_dir, replay_date, e.ticker, tz) for e in watchlist}
    watchlist = [e for e in watchlist if bars_by_ticker.get(e.ticker)]
    if not watchlist:
        raise ReplayError("No recorded bars found for any watchlist ticker; nothing to replay.")

    events: list[tuple[datetime, str, Candle]] = []
    for ticker, candles in bars_by_ticker.items():
        for c in candles:
            events.append((c.timestamp, ticker, c))
    events.sort(key=lambda e: e[0])

    market_open = events[0][0]
    market_close = events[-1][0]
    session = build_session_info(replay_date, market_open, market_close, tz)
    state = build_day_state(config, session, SYNTHETIC_STARTING_EQUITY, SYNTHETIC_STARTING_EQUITY)
    freeze_watchlist(state, watchlist)
    execution = ReplayExecutionEngine()

    result, exit_code = "normal_close", EXIT_OK
    for now, ticker, candle in events:
        execution.set_last_price(ticker, candle.close)
        on_new_candle(ticker, candle, now, state, config, execution, journal)

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
    else:
        # Ran out of recorded bars before any terminal trigger fired.
        flatten_all(state, ExitReason.FORCE_CLOSE, config, execution, journal, events[-1][0])

    report = build_report(
        DailyReportInputs(
            run_date=replay_date, mode=f"REPLAY ({config.mode})",
            starting_equity=SYNTHETIC_STARTING_EQUITY, ending_equity=state.equity,
            watchlist=watchlist, claude_cost_usd=0.0, claude_notes="(--replay: Claude call skipped)",
            zero_trade_day=False,
        ),
        journal,
    )
    report_path = save_report(config.paths.reports_dir, replay_date, report)
    journal.append_run_summary(f"REPLAY-{config.mode}", result, 0.0, state.equity - SYNTHETIC_STARTING_EQUITY)

    logger.info("Replay complete: result=%s pnl=%.2f report=%s", result, state.equity - SYNTHETIC_STARTING_EQUITY, report_path)
    print(f"Replay complete. Result: {result}. P&L: ${state.equity - SYNTHETIC_STARTING_EQUITY:,.2f}. Report: {report_path}")
    return exit_code
