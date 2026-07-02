"""Engine entry-gate tests: every bar must produce a traceable outcome (a
skip reason or an entry), gates fire in the documented order (pattern ->
VWAP -> MACD -> RVOL -> catalyst), and RVOL/catalyst are never silently
skipped when data is missing.

Indicator math (VWAP/MACD/RVOL formulas) already has -- or doesn't need --
its own numeric torture tests here; these tests monkeypatch `indicators`
and `patterns` so each gate can be isolated deterministically without
fighting realistic OHLCV shapes for every combination.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from trader import engine, indicators, patterns
from trader.config import AnthropicConfig, Config, MACDConfig, Paths, PatternToggles
from trader.execution import ReplayExecutionEngine
from trader.journal import Journal
from trader.market_calendar import SessionInfo
from trader.models import Candle, WatchlistEntry

_BASE = datetime(2026, 7, 2, 9, 30)


def _candle(minute: int, price: float = 10.0, volume: float = 1000) -> Candle:
    return Candle(timestamp=_BASE + timedelta(minutes=minute), open=price, high=price, low=price, close=price, volume=volume)


def _config(tmp_path, **overrides) -> Config:
    defaults = dict(
        mode="DRY_RUN", timezone="America/New_York",
        daily_kill_switch_pct=-10, max_positions=5, risk_per_trade_pct=2,
        max_position_pct_bp=25, daily_profit_giveback_pct=25, no_trade_cutoff_hours=2,
        stop_loss_pct=1, take_profit_pct=3, trail_off_trigger_pct=1.5, trail_off_scale_out_pct=25,
        force_close_offset_min=5, watchlist_size=5, price_min=2, price_max=20, min_rvol=5,
        max_float_millions=20, require_news_catalyst=True, overextension_pct=3, z_hour_cutoff=1.0,
        alpaca_data_feed="iex",
        macd=MACDConfig(fast=1, slow=2, signal=1),  # min_bars_for_macd == 3, keeps fixtures tiny
        patterns=PatternToggles(),
        anthropic=AnthropicConfig(),
        paths=Paths(
            base_dir=tmp_path, journal_dir=tmp_path / "journal", logs_dir=tmp_path / "logs",
            replay_dir=tmp_path / "replay", performance_db=tmp_path / "performance_db.json",
            runs_csv=tmp_path / "runs.csv", reports_dir=tmp_path,
        ),
    )
    defaults.update(overrides)
    return Config(**defaults)


def _entry(ticker="DSY", catalyst="Q2 earnings beat", baseline=1000.0) -> WatchlistEntry:
    return WatchlistEntry(ticker=ticker, reason="test", catalyst=catalyst, rank=1, avg_volume_baseline=baseline)


def _state(config: Config, entry: WatchlistEntry, is_replay: bool = False) -> engine.DayState:
    session = SessionInfo(
        session_date=_BASE.date(), market_open=_BASE, market_close=_BASE + timedelta(hours=6, minutes=30),
        is_open=True, is_early_close=False,
    )
    state = engine.build_day_state(config, session, starting_equity=100_000, buying_power=100_000)
    state.is_replay = is_replay
    engine.freeze_watchlist(state, [entry])
    return state


def _patch_gates(monkeypatch, *, pattern=True, pct_above_vwap=1.0, macd_bullish=True, rvol=10.0):
    if pattern:
        fake_candle = _candle(0)
        fake_match = patterns.PatternMatch("fake_pattern", (fake_candle,), entry_price=fake_candle.close)
        monkeypatch.setattr(engine.patterns, "detect_all", lambda *a, **k: [fake_match])
    else:
        monkeypatch.setattr(engine.patterns, "detect_all", lambda *a, **k: [])
    monkeypatch.setattr(engine.indicators, "pct_above_vwap", lambda price, vwap_value: pct_above_vwap)
    monkeypatch.setattr(engine.indicators, "macd_is_bullish", lambda *a, **k: macd_bullish)
    monkeypatch.setattr(engine.indicators, "relative_volume", lambda current, baseline: rvol)


def _warm_up(state: engine.DayState, ticker: str, n: int) -> None:
    """Directly seeds `n` bars of history/VWAP without running the entry
    gates, so a test can get past the `missing_bars` MACD-readiness floor
    before exercising the gate it actually cares about."""
    history = state.candle_history.setdefault(ticker, [])
    vwap_values = state.vwap_history.setdefault(ticker, [])
    for i in range(n):
        c = _candle(i)
        history.append(c)
        vwap_values.append(indicators.vwap(history))
        state.high_of_day[ticker] = max(state.high_of_day.get(ticker, c.high), c.high)


def _run_bars(state, config, journal, ticker, n, start_index=0, execution=None):
    execution = execution or ReplayExecutionEngine()
    for i in range(start_index, start_index + n):
        candle = _candle(i, price=10.0 + i * 0.01, volume=1000)
        if hasattr(execution, "set_last_price"):
            execution.set_last_price(ticker, candle.close)
        engine.on_new_candle(ticker, candle, candle.timestamp, state, config, execution, journal)
    return execution


def test_no_pattern_is_logged_not_silent(tmp_path):
    """This is the exact DSY bug: a bar that fails pattern detection must
    leave a traceable skip, never a silent no-op."""
    config = _config(tmp_path)
    entry = _entry()
    state = _state(config, entry)
    journal = Journal(config.paths, _BASE.date())

    # Boring flat candles never satisfy any real pattern detector.
    _run_bars(state, config, journal, entry.ticker, n=5)

    counts = journal.skip_reason_counts()
    assert counts == {"no_pattern": 5}


def test_missing_bars_before_macd_is_computable(tmp_path, monkeypatch):
    config = _config(tmp_path)  # min_bars_for_macd == 3
    entry = _entry()
    state = _state(config, entry)
    journal = Journal(config.paths, _BASE.date())
    _patch_gates(monkeypatch, pattern=True)

    _run_bars(state, config, journal, entry.ticker, n=2)  # only 2 bars < 3 needed

    counts = journal.skip_reason_counts()
    assert counts == {"missing_bars": 2}


def test_below_vwap_logged(tmp_path, monkeypatch):
    # below_vwap/overextended fire ahead of the MACD-readiness check, so no
    # warm-up bars are needed here -- they're evaluated on the very first bar.
    config = _config(tmp_path)
    entry = _entry()
    state = _state(config, entry)
    journal = Journal(config.paths, _BASE.date())
    _patch_gates(monkeypatch, pattern=True, pct_above_vwap=-0.5)

    _run_bars(state, config, journal, entry.ticker, n=3)

    counts = journal.skip_reason_counts()
    assert counts == {"below_vwap": 3}


def test_overextended_logged(tmp_path, monkeypatch):
    config = _config(tmp_path, overextension_pct=3)
    entry = _entry()
    state = _state(config, entry)
    journal = Journal(config.paths, _BASE.date())
    _patch_gates(monkeypatch, pattern=True, pct_above_vwap=5.0)

    _run_bars(state, config, journal, entry.ticker, n=3)

    counts = journal.skip_reason_counts()
    assert counts == {"overextended": 3}


def test_macd_negative_logged(tmp_path, monkeypatch):
    config = _config(tmp_path)  # min_bars_for_macd == 3
    entry = _entry()
    state = _state(config, entry)
    journal = Journal(config.paths, _BASE.date())
    _patch_gates(monkeypatch, pattern=True, pct_above_vwap=1.0, macd_bullish=False)

    _warm_up(state, entry.ticker, 2)  # get past missing_bars first
    _run_bars(state, config, journal, entry.ticker, n=3, start_index=2)

    counts = journal.skip_reason_counts()
    assert counts == {"macd_negative": 3}


def test_missing_rvol_baseline_logged_not_conflated_with_rvol_low(tmp_path, monkeypatch):
    config = _config(tmp_path)
    entry = _entry(baseline=None)  # fixture predates baseline recording
    state = _state(config, entry)
    journal = Journal(config.paths, _BASE.date())
    _patch_gates(monkeypatch, pattern=True, pct_above_vwap=1.0, macd_bullish=True)

    _warm_up(state, entry.ticker, 2)
    _run_bars(state, config, journal, entry.ticker, n=3, start_index=2)

    counts = journal.skip_reason_counts()
    assert counts == {"missing_rvol_baseline": 3}


def test_rvol_low_logged(tmp_path, monkeypatch):
    config = _config(tmp_path, min_rvol=5)
    entry = _entry(baseline=1000.0)
    state = _state(config, entry)
    journal = Journal(config.paths, _BASE.date())
    _patch_gates(monkeypatch, pattern=True, pct_above_vwap=1.0, macd_bullish=True, rvol=1.2)

    _warm_up(state, entry.ticker, 2)
    _run_bars(state, config, journal, entry.ticker, n=3, start_index=2)

    counts = journal.skip_reason_counts()
    assert counts == {"rvol_low": 3}


def test_no_catalyst_logged_in_live_mode(tmp_path, monkeypatch):
    config = _config(tmp_path, require_news_catalyst=True)
    entry = _entry(catalyst="n/a")
    state = _state(config, entry, is_replay=False)
    journal = Journal(config.paths, _BASE.date())
    _patch_gates(monkeypatch, pattern=True, pct_above_vwap=1.0, macd_bullish=True, rvol=10.0)

    _warm_up(state, entry.ticker, 2)
    _run_bars(state, config, journal, entry.ticker, n=1, start_index=2)

    counts = journal.skip_reason_counts()
    assert counts == {"no_catalyst": 1}
    assert state.entries_made == 0


def test_catalyst_gate_bypassed_in_replay_with_logged_notice(tmp_path, monkeypatch, caplog):
    config = _config(tmp_path, require_news_catalyst=True)
    entry = _entry(catalyst="n/a")  # recorded fixtures always have this placeholder
    state = _state(config, entry, is_replay=True)
    journal = Journal(config.paths, _BASE.date())
    _patch_gates(monkeypatch, pattern=True, pct_above_vwap=1.0, macd_bullish=True, rvol=10.0)

    _warm_up(state, entry.ticker, 2)
    with caplog.at_level("INFO", logger="trader.engine"):
        _run_bars(state, config, journal, entry.ticker, n=1, start_index=2)

    # Never silently failed: an entry actually happens, and the bypass is
    # logged (not just swallowed).
    assert journal.skip_reason_counts() == {}
    assert state.entries_made == 1
    assert any("bypassing require_news_catalyst" in r.message for r in caplog.records)


def test_catalyst_bypass_notice_logged_once_per_ticker(tmp_path, monkeypatch, caplog):
    config = _config(tmp_path, require_news_catalyst=True)
    entry = _entry(catalyst="n/a")
    state = _state(config, entry, is_replay=True)
    journal = Journal(config.paths, _BASE.date())
    _patch_gates(monkeypatch, pattern=True, pct_above_vwap=1.0, macd_bullish=True, rvol=10.0)

    _warm_up(state, entry.ticker, 2)
    with caplog.at_level("INFO", logger="trader.engine"):
        # The first of these bars enters a position (satisfies every gate),
        # so bars 2-5 go through position-exit management, not the entry
        # gates again -- the bypass notice must not repeat per bar.
        _run_bars(state, config, journal, entry.ticker, n=5, start_index=2)

    bypass_logs = [r for r in caplog.records if "bypassing require_news_catalyst" in r.message]
    assert len(bypass_logs) == 1


def test_all_gates_pass_results_in_entry(tmp_path, monkeypatch):
    config = _config(tmp_path, require_news_catalyst=True)
    entry = _entry(catalyst="Q2 earnings beat", baseline=1000.0)
    state = _state(config, entry)
    journal = Journal(config.paths, _BASE.date())
    _patch_gates(monkeypatch, pattern=True, pct_above_vwap=1.0, macd_bullish=True, rvol=10.0)

    _warm_up(state, entry.ticker, 2)
    _run_bars(state, config, journal, entry.ticker, n=1, start_index=2)

    assert journal.skip_reason_counts() == {}
    assert state.entries_made == 1
    assert entry.ticker in state.positions


def test_kill_switch_and_no_trade_cutoff_states_are_logged_not_silent(tmp_path):
    config = _config(tmp_path)
    entry = _entry()
    state = _state(config, entry)
    journal = Journal(config.paths, _BASE.date())

    state.kill_switch_hit = True
    _run_bars(state, config, journal, entry.ticker, n=2)
    state.kill_switch_hit = False
    state.no_trade_cutoff_hit = True
    _run_bars(state, config, journal, entry.ticker, n=3)

    counts = journal.skip_reason_counts()
    assert counts == {"kill_switch_hit": 2, "no_trade_cutoff_hit": 3}
