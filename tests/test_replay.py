"""Integration tests for `--replay`: cutoff semantics must be driven entirely
by the fixture's own recorded bar timestamps, never by the wall clock the
test happens to run at, and no_trade_cutoff must be one account-wide counter
shared across every watchlist ticker, not per-ticker."""

from __future__ import annotations

import csv
import json
from datetime import date, datetime, timedelta
from pathlib import Path

from trader.config import AnthropicConfig, Config, MACDConfig, Paths, PatternToggles
from trader.replay import run_replay

TZ_NAME = "America/New_York"
REPLAY_DATE = date(2026, 7, 2)


def _config(tmp_path: Path, **overrides) -> Config:
    defaults = dict(
        mode="DRY_RUN", timezone=TZ_NAME,
        daily_kill_switch_pct=-10, max_positions=5, risk_per_trade_pct=2,
        max_position_pct_bp=25, daily_profit_giveback_pct=25, no_trade_cutoff_hours=2,
        stop_loss_pct=1, take_profit_pct=3, trail_off_trigger_pct=1.5, trail_off_scale_out_pct=25,
        force_close_offset_min=5, watchlist_size=5, price_min=2, price_max=20, min_rvol=5,
        max_float_millions=20, require_news_catalyst=True, overextension_pct=3, z_hour_cutoff=1.0,
        alpaca_data_feed="iex",
        macd=MACDConfig(), patterns=PatternToggles(), anthropic=AnthropicConfig(),
        paths=Paths(
            base_dir=tmp_path, journal_dir=tmp_path / "journal", logs_dir=tmp_path / "logs",
            replay_dir=tmp_path / "replay", performance_db=tmp_path / "performance_db.json",
            runs_csv=tmp_path / "runs.csv", reports_dir=tmp_path,
        ),
    )
    defaults.update(overrides)
    return Config(**defaults)


def _flat_bars(start: datetime, n_minutes: int, price: float = 10.0, volume: float = 1000) -> list[dict]:
    """Bars with no discernible pattern -- never a real entry -- so the only
    thing that can end the day is the no_trade_cutoff / force_close logic
    under test, not a coincidental trade."""
    return [
        {
            "timestamp": (start + timedelta(minutes=i)).isoformat(),
            "open": price, "high": price, "low": price, "close": price, "volume": volume,
        }
        for i in range(n_minutes)
    ]


def _write_fixture(replay_dir: Path, tickers_bars: dict[str, list[dict]], catalyst: str = "n/a") -> None:
    replay_dir.mkdir(parents=True, exist_ok=True)
    watchlist = [
        {"ticker": ticker, "reason": "test fixture", "catalyst": catalyst, "rank": i + 1, "avg_volume_baseline": 1_000_000}
        for i, ticker in enumerate(tickers_bars)
    ]
    (replay_dir / f"{REPLAY_DATE.isoformat()}-watchlist.json").write_text(json.dumps(watchlist), encoding="utf-8")
    for ticker, bars in tickers_bars.items():
        (replay_dir / f"{REPLAY_DATE.isoformat()}-{ticker}.json").write_text(json.dumps(bars), encoding="utf-8")


def _last_run_result(runs_csv: Path) -> str:
    with open(runs_csv, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    return rows[-1]["result"]


def test_no_trade_cutoff_driven_by_simulated_bar_time_not_wall_clock(tmp_path, monkeypatch):
    market_open = datetime(2026, 7, 2, 9, 30)
    # 130 minutes of boring, no-pattern bars spans past the 2-hour cutoff
    # (11:30) recorded in *fixture* time.
    bars = _flat_bars(market_open, n_minutes=130)
    config = _config(tmp_path, no_trade_cutoff_hours=2)
    _write_fixture(config.paths.replay_dir, {"ZZZ": bars})

    class _FakeDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            # A wall clock wildly different from the fixture's 2026-07-02
            # session -- if any cutoff decision leaked wall-clock in, this
            # would change the outcome.
            real_now = datetime(2099, 1, 1, 3, 0, 0)
            return real_now.replace(tzinfo=tz) if tz else real_now

    monkeypatch.setattr("trader.journal.datetime", _FakeDatetime)

    run_replay(config, REPLAY_DATE)

    assert _last_run_result(config.paths.runs_csv) == "no_trade_cutoff"


def test_no_trade_cutoff_never_fires_once_any_bar_confirms_wall_clock_is_unused(tmp_path):
    """Same fixture, no wall-clock monkeypatching at all: confirms the
    baseline (unpatched) result matches, so the prior test's assertion is
    actually about wall-clock independence and not a coincidence."""
    market_open = datetime(2026, 7, 2, 9, 30)
    bars = _flat_bars(market_open, n_minutes=130)
    config = _config(tmp_path, no_trade_cutoff_hours=2)
    _write_fixture(config.paths.replay_dir, {"ZZZ": bars})

    run_replay(config, REPLAY_DATE)

    assert _last_run_result(config.paths.runs_csv) == "no_trade_cutoff"


def test_no_trade_cutoff_is_account_wide_across_watchlist_tickers(tmp_path, monkeypatch):
    """If ANY ticker enters, the no_trade_cutoff clock stops for the whole
    account -- a second ticker that never itself finds a pattern must not
    independently trigger it."""
    from trader import engine, patterns

    market_open = datetime(2026, 7, 2, 9, 30)
    # AAA's very first bar is tagged with a sentinel volume the fake pattern
    # detector recognizes as "the entry signal"; BBB never matches anything.
    aaa_bars = _flat_bars(market_open, n_minutes=130, price=10.0, volume=999_999)
    bbb_bars = _flat_bars(market_open, n_minutes=130, price=10.0, volume=1000)
    config = _config(tmp_path, no_trade_cutoff_hours=2, require_news_catalyst=False, min_rvol=0)
    _write_fixture(config.paths.replay_dir, {"AAA": aaa_bars, "BBB": bbb_bars})

    real_detect_all = patterns.detect_all

    def _fake_detect_all(history, **kwargs):
        if history and history[-1].volume == 999_999:
            fake_candle = history[-1]
            return [patterns.PatternMatch("fake_pattern", (fake_candle,), entry_price=fake_candle.close)]
        return real_detect_all(history, **kwargs)

    monkeypatch.setattr(engine.patterns, "detect_all", _fake_detect_all)
    monkeypatch.setattr(engine.indicators, "pct_above_vwap", lambda price, vwap_value: 1.0)
    monkeypatch.setattr(engine.indicators, "macd_is_bullish", lambda *a, **k: True)
    monkeypatch.setattr(engine.indicators, "relative_volume", lambda current, baseline: 10.0)

    run_replay(config, REPLAY_DATE)

    result = _last_run_result(config.paths.runs_csv)
    assert result != "no_trade_cutoff", (
        "AAA entered a position well before the cutoff; the shared account-wide "
        "entries_made counter should have prevented no_trade_cutoff from firing "
        "for BBB (or the account) afterward."
    )
