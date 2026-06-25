"""
Section 18: Daily giveback exit mode tests.

All tests use pure Python with no live network calls.
The circuit-breaker function (check_daily_limits) is called directly for
unit tests; session-level tests use the existing FakeClock / ConfigurableMarketClient
fixtures from conftest.
"""

from __future__ import annotations

import pytest

from bot.engine.circuit_breaker import DailyAction, DailyState, check_daily_limits
from bot.engine.config import ExecutionConfig

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _state(equity: float = 2_000.0) -> DailyState:
    return DailyState(day_start_equity=equity)


def _cfg_giveback(
    target_pct: float = 10.0,
    giveback_pct: float = 25.0,
    max_loss_pct: float = -10.0,
    flatten_on_max_loss: bool = True,
) -> ExecutionConfig:
    return ExecutionConfig(
        daily_target_mode="giveback",
        daily_profit_target_pct=target_pct,
        daily_giveback_pct=giveback_pct,
        daily_max_loss_pct=max_loss_pct,
        flatten_on_max_loss=flatten_on_max_loss,
    )


def _cfg_stop(
    target_pct: float = 10.0,
    flatten: bool = True,
) -> ExecutionConfig:
    return ExecutionConfig(
        daily_target_mode="stop",
        daily_profit_target_pct=target_pct,
        flatten_on_profit_target=flatten,
    )


def _call(
    state: DailyState,
    realized: float,
    unrealized: float,
    cfg: ExecutionConfig,
) -> DailyAction:
    return check_daily_limits(state, realized, unrealized, cfg)


# ---------------------------------------------------------------------------
# Arming: armed exactly when daily_pl_pct first hits the threshold
# ---------------------------------------------------------------------------


class TestArming:
    def test_not_armed_below_threshold(self) -> None:
        # day_start = 2000, target = 10% → need $200 profit
        # $199 of profit → 9.95% → not armed
        state = _state(2_000.0)
        cfg = _cfg_giveback(target_pct=10.0)
        action = _call(state, realized=199.0, unrealized=0.0, cfg=cfg)
        assert action == DailyAction.NONE
        assert not state.giveback_armed

    def test_armed_exactly_at_threshold(self) -> None:
        # $200 of profit → exactly 10% → armed
        state = _state(2_000.0)
        cfg = _cfg_giveback(target_pct=10.0)
        action = _call(state, realized=200.0, unrealized=0.0, cfg=cfg)
        assert action == DailyAction.NONE  # arm but don't halt
        assert state.giveback_armed

    def test_armed_above_threshold(self) -> None:
        state = _state(2_000.0)
        cfg = _cfg_giveback(target_pct=10.0)
        action = _call(state, realized=500.0, unrealized=0.0, cfg=cfg)
        assert state.giveback_armed
        # Still no halt since $500 < $500 × 0.75 = $375 is false (500 > 375)
        assert action == DailyAction.NONE

    def test_arm_happens_once(self) -> None:
        # Arm on cycle 1, still armed on cycle 2 without re-triggering
        state = _state(2_000.0)
        cfg = _cfg_giveback(target_pct=10.0)
        _call(state, realized=200.0, unrealized=0.0, cfg=cfg)
        assert state.giveback_armed
        # Second cycle with slightly lower profit — still armed (never un-arms)
        action = _call(state, realized=195.0, unrealized=0.0, cfg=cfg)
        assert state.giveback_armed
        # No trigger fired because daily_pl_high is 200 and 195 > 200 * 0.75 = 150
        assert action == DailyAction.NONE

    def test_stop_mode_does_not_arm_giveback(self) -> None:
        # In stop mode the giveback fields are unused
        state = _state(2_000.0)
        cfg = _cfg_stop(target_pct=10.0, flatten=True)
        action = _call(state, realized=300.0, unrealized=0.0, cfg=cfg)
        assert action == DailyAction.FLATTEN_AND_HALT
        assert not state.giveback_armed


# ---------------------------------------------------------------------------
# Keeps trading while armed (no halt until trigger)
# ---------------------------------------------------------------------------


class TestKeepsTradingWhileArmed:
    def test_no_halt_while_above_trigger(self) -> None:
        # peak = 1000, giveback 25% → trigger = 750
        # current = 900 → above trigger → continue
        state = _state(2_000.0)
        cfg = _cfg_giveback(target_pct=10.0, giveback_pct=25.0)
        # Arm and push to a peak
        _call(state, realized=1_000.0, unrealized=0.0, cfg=cfg)
        assert state.giveback_armed
        assert state.daily_pl_high == pytest.approx(1_000.0)
        # Retrace slightly but stay above trigger
        action = _call(state, realized=900.0, unrealized=0.0, cfg=cfg)
        assert action == DailyAction.NONE
        assert not state.halted

    def test_peak_tracks_new_highs(self) -> None:
        state = _state(2_000.0)
        cfg = _cfg_giveback(target_pct=10.0, giveback_pct=25.0)
        _call(state, realized=200.0, unrealized=0.0, cfg=cfg)  # arm
        _call(state, realized=600.0, unrealized=0.0, cfg=cfg)
        assert state.daily_pl_high == pytest.approx(600.0)
        _call(state, realized=800.0, unrealized=0.0, cfg=cfg)
        assert state.daily_pl_high == pytest.approx(800.0)
        _call(state, realized=1_000.0, unrealized=0.0, cfg=cfg)
        assert state.daily_pl_high == pytest.approx(1_000.0)
        # Retrace — peak stays at 1000
        _call(state, realized=900.0, unrealized=0.0, cfg=cfg)
        assert state.daily_pl_high == pytest.approx(1_000.0)


# ---------------------------------------------------------------------------
# Giveback exit — worked example from spec
# day_start_equity=$2000, target_pct=10%, giveback_pct=25%
# Arm at $200, peak $1000, trigger=$750
# ---------------------------------------------------------------------------


class TestGivebackExit:
    def _build_state(self) -> tuple[DailyState, ExecutionConfig]:
        state = _state(2_000.0)
        cfg = _cfg_giveback(target_pct=10.0, giveback_pct=25.0)
        return state, cfg

    def test_arm_at_200(self) -> None:
        state, cfg = self._build_state()
        action = _call(state, realized=200.0, unrealized=0.0, cfg=cfg)
        assert state.giveback_armed
        assert action == DailyAction.NONE

    def test_no_halt_at_peak(self) -> None:
        state, cfg = self._build_state()
        _call(state, realized=200.0, unrealized=0.0, cfg=cfg)
        action = _call(state, realized=1_000.0, unrealized=0.0, cfg=cfg)
        assert state.daily_pl_high == pytest.approx(1_000.0)
        # trigger = 750; 1000 > 750 → still running
        assert action == DailyAction.NONE

    def test_no_halt_just_above_trigger(self) -> None:
        state, cfg = self._build_state()
        _call(state, realized=200.0, unrealized=0.0, cfg=cfg)
        _call(state, realized=1_000.0, unrealized=0.0, cfg=cfg)
        # $751 is above trigger ($750) → no halt
        action = _call(state, realized=751.0, unrealized=0.0, cfg=cfg)
        assert action == DailyAction.NONE

    def test_flatten_and_halt_at_trigger(self) -> None:
        state, cfg = self._build_state()
        _call(state, realized=200.0, unrealized=0.0, cfg=cfg)
        _call(state, realized=1_000.0, unrealized=0.0, cfg=cfg)
        # $750 == trigger → FLATTEN_AND_HALT
        action = _call(state, realized=750.0, unrealized=0.0, cfg=cfg)
        assert action == DailyAction.FLATTEN_AND_HALT
        assert state.halted
        assert "giveback triggered" in state.halt_reason

    def test_flatten_and_halt_below_trigger(self) -> None:
        state, cfg = self._build_state()
        _call(state, realized=200.0, unrealized=0.0, cfg=cfg)
        _call(state, realized=1_000.0, unrealized=0.0, cfg=cfg)
        action = _call(state, realized=400.0, unrealized=0.0, cfg=cfg)
        assert action == DailyAction.FLATTEN_AND_HALT

    def test_trigger_includes_unrealized(self) -> None:
        # total_pnl = realized + unrealized
        state, cfg = self._build_state()
        _call(state, realized=200.0, unrealized=0.0, cfg=cfg)
        # Peak via unrealized
        _call(state, realized=500.0, unrealized=500.0, cfg=cfg)  # total = 1000
        assert state.daily_pl_high == pytest.approx(1_000.0)
        # Now realized drops, unrealized gone: total = 400 < 750
        action = _call(state, realized=400.0, unrealized=0.0, cfg=cfg)
        assert action == DailyAction.FLATTEN_AND_HALT

    def test_already_halted_after_trigger(self) -> None:
        state, cfg = self._build_state()
        _call(state, realized=200.0, unrealized=0.0, cfg=cfg)
        _call(state, realized=1_000.0, unrealized=0.0, cfg=cfg)
        _call(state, realized=750.0, unrealized=0.0, cfg=cfg)
        assert state.halted
        # Subsequent calls return HALT (not FLATTEN_AND_HALT again)
        action = _call(state, realized=900.0, unrealized=0.0, cfg=cfg)
        assert action == DailyAction.HALT


# ---------------------------------------------------------------------------
# Trigger trails upward as new highs are made
# ---------------------------------------------------------------------------


class TestTrailingTrigger:
    def test_trigger_rises_with_new_highs(self) -> None:
        state = _state(2_000.0)
        cfg = _cfg_giveback(target_pct=10.0, giveback_pct=25.0)
        _call(state, realized=200.0, unrealized=0.0, cfg=cfg)   # arm

        # Peak 1: $500 → trigger = $375
        _call(state, realized=500.0, unrealized=0.0, cfg=cfg)
        assert state.daily_pl_high == pytest.approx(500.0)

        # $400 > $375 → no halt
        action = _call(state, realized=400.0, unrealized=0.0, cfg=cfg)
        assert action == DailyAction.NONE

        # New high: $800 → trigger = $600
        _call(state, realized=800.0, unrealized=0.0, cfg=cfg)
        assert state.daily_pl_high == pytest.approx(800.0)

        # $400 < $600 → now triggers
        action = _call(state, realized=400.0, unrealized=0.0, cfg=cfg)
        assert action == DailyAction.FLATTEN_AND_HALT


# ---------------------------------------------------------------------------
# Never armed: day stays below threshold — no profit-side stop
# ---------------------------------------------------------------------------


class TestNeverArmed:
    def test_no_profit_stop_when_not_armed(self) -> None:
        state = _state(2_000.0)
        cfg = _cfg_giveback(target_pct=10.0, giveback_pct=25.0)
        # Day stays below activation (< $200 profit)
        for pnl in [50.0, 100.0, 150.0, 180.0, 190.0]:
            action = _call(state, realized=pnl, unrealized=0.0, cfg=cfg)
            assert action == DailyAction.NONE
        assert not state.giveback_armed
        assert not state.halted

    def test_max_loss_still_fires_when_not_armed(self) -> None:
        state = _state(2_000.0)
        cfg = _cfg_giveback(target_pct=10.0, giveback_pct=25.0, max_loss_pct=-10.0, flatten_on_max_loss=True)
        # Loss of 10% = -$200
        action = _call(state, realized=-200.0, unrealized=0.0, cfg=cfg)
        assert action == DailyAction.FLATTEN_AND_HALT
        assert state.halted


# ---------------------------------------------------------------------------
# Stop mode: unchanged hard-stop behavior
# ---------------------------------------------------------------------------


class TestStopMode:
    def test_hard_stop_with_flatten(self) -> None:
        state = _state(100_000.0)
        cfg = _cfg_stop(target_pct=3.0, flatten=True)
        action = _call(state, realized=3_100.0, unrealized=0.0, cfg=cfg)
        assert action == DailyAction.FLATTEN_AND_HALT
        assert state.halted

    def test_hard_stop_halt_only(self) -> None:
        state = _state(100_000.0)
        cfg = _cfg_stop(target_pct=3.0, flatten=False)
        action = _call(state, realized=3_100.0, unrealized=0.0, cfg=cfg)
        assert action == DailyAction.HALT
        assert state.halted

    def test_exactly_at_target(self) -> None:
        state = _state(100_000.0)
        cfg = _cfg_stop(target_pct=3.0, flatten=True)
        action = _call(state, realized=3_000.0, unrealized=0.0, cfg=cfg)
        assert action == DailyAction.FLATTEN_AND_HALT

    def test_below_target_continues(self) -> None:
        state = _state(100_000.0)
        cfg = _cfg_stop(target_pct=3.0, flatten=True)
        action = _call(state, realized=2_500.0, unrealized=0.0, cfg=cfg)
        assert action == DailyAction.NONE

    def test_stop_mode_no_giveback_fields_used(self) -> None:
        state = _state(100_000.0)
        cfg = _cfg_stop(target_pct=3.0, flatten=True)
        _call(state, realized=3_000.0, unrealized=0.0, cfg=cfg)
        # Giveback state untouched
        assert not state.giveback_armed
        assert state.daily_pl_high == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Restart persistence: rebuilding DailyState mid-day
# ---------------------------------------------------------------------------


class TestRestartPersistence:
    def test_preserved_state_continues_correctly(self) -> None:
        # Simulate a session that armed and reached a peak, then restarts
        original = _state(2_000.0)
        cfg = _cfg_giveback(target_pct=10.0, giveback_pct=25.0)
        _call(original, realized=200.0, unrealized=0.0, cfg=cfg)  # arm
        _call(original, realized=800.0, unrealized=0.0, cfg=cfg)  # set peak

        # "Persist" and reconstruct DailyState
        restored = DailyState(
            day_start_equity=original.day_start_equity,
            realized_pnl=original.realized_pnl,
            unrealized_pnl=original.unrealized_pnl,
            daily_pl_high=original.daily_pl_high,
            giveback_armed=original.giveback_armed,
            halted=original.halted,
        )

        assert restored.giveback_armed
        assert restored.daily_pl_high == pytest.approx(800.0)

        # trigger = 800 * 0.75 = 600; current 700 > 600 → still running
        action = _call(restored, realized=700.0, unrealized=0.0, cfg=cfg)
        assert action == DailyAction.NONE

        # Drop to 500 < 600 → halt
        action = _call(restored, realized=500.0, unrealized=0.0, cfg=cfg)
        assert action == DailyAction.FLATTEN_AND_HALT

    def test_new_day_reset_clears_state(self) -> None:
        # At new-day start, DailyState is constructed fresh → all fields reset
        fresh = DailyState(day_start_equity=3_000.0)
        assert not fresh.giveback_armed
        assert fresh.daily_pl_high == pytest.approx(0.0)
        assert not fresh.halted

    def test_giveback_armed_persisted(self) -> None:
        original = _state(2_000.0)
        cfg = _cfg_giveback(target_pct=10.0, giveback_pct=25.0)
        _call(original, realized=200.0, unrealized=0.0, cfg=cfg)
        assert original.giveback_armed

        # Restore with armed=True — new cycle sees it as armed
        restored = DailyState(
            day_start_equity=original.day_start_equity,
            daily_pl_high=original.daily_pl_high,
            giveback_armed=True,
        )
        # Now send a tiny realization — still armed, but peak is tiny so trigger is tiny
        # $150 < $200 * 0.75 = $150 → triggers exactly at boundary
        action = _call(restored, realized=150.0, unrealized=0.0, cfg=cfg)
        assert action == DailyAction.FLATTEN_AND_HALT


# ---------------------------------------------------------------------------
# Interaction: max-loss and giveback coexist
# ---------------------------------------------------------------------------


class TestInteractions:
    def test_max_loss_takes_priority_over_armed_giveback(self) -> None:
        state = _state(2_000.0)
        cfg = _cfg_giveback(target_pct=10.0, giveback_pct=25.0, max_loss_pct=-10.0, flatten_on_max_loss=True)
        # Arm first
        _call(state, realized=200.0, unrealized=0.0, cfg=cfg)
        assert state.giveback_armed
        # Then hit max-loss
        action = _call(state, realized=-200.0, unrealized=0.0, cfg=cfg)
        assert action == DailyAction.FLATTEN_AND_HALT
        assert "max loss" in state.halt_reason

    def test_giveback_mode_ignores_flatten_on_profit_target(self) -> None:
        # flatten_on_profit_target should have no effect in giveback mode
        state = _state(2_000.0)
        cfg = ExecutionConfig(
            daily_target_mode="giveback",
            daily_profit_target_pct=10.0,
            daily_giveback_pct=25.0,
            flatten_on_profit_target=True,  # irrelevant in giveback mode
        )
        # Cross activation threshold — should arm, NOT halt
        action = _call(state, realized=200.0, unrealized=0.0, cfg=cfg)
        assert action == DailyAction.NONE
        assert state.giveback_armed


# ---------------------------------------------------------------------------
# Settings round-trip: new fields stored and retrieved via handlers
# ---------------------------------------------------------------------------


class TestGivebackSettingsHandlers:
    def test_default_daily_target_mode_is_giveback(self) -> None:
        import sqlite3

        from bot.control.handlers import handle_get_settings

        conn = sqlite3.connect(":memory:", check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.executescript(
            """
            CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at INTEGER NOT NULL);
            INSERT INTO settings VALUES ('daily_target_mode', 'giveback', 1);
            INSERT INTO settings VALUES ('daily_giveback_pct', '25.0', 1);
            """
        )
        result = handle_get_settings(conn, {})
        assert result["daily_target_mode"] == "giveback"
        assert result["daily_giveback_pct"] == pytest.approx(25.0)

    def test_update_daily_target_mode(self) -> None:
        import sqlite3

        from bot.control.handlers import handle_update_settings

        conn = sqlite3.connect(":memory:", check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.executescript(
            """
            CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at INTEGER NOT NULL);
            INSERT INTO settings VALUES ('daily_target_mode', 'giveback', 1);
            INSERT INTO settings VALUES ('daily_giveback_pct', '25.0', 1);
            INSERT INTO settings VALUES ('daily_risk_pct', '5.0', 1);
            INSERT INTO settings VALUES ('max_positions', '5', 1);
            INSERT INTO settings VALUES ('risk_override_enabled', 'false', 1);
            INSERT INTO settings VALUES ('risk_per_trade_pct', '1.0', 1);
            """
        )
        result = handle_update_settings(conn, {"patch": {"daily_target_mode": "stop", "daily_giveback_pct": 30.0}})
        assert result["daily_target_mode"] == "stop"
        assert result["daily_giveback_pct"] == pytest.approx(30.0)

    def test_giveback_pct_round_trips(self) -> None:
        import sqlite3

        from bot.control.handlers import handle_get_settings, handle_update_settings

        conn = sqlite3.connect(":memory:", check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.executescript(
            """
            CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at INTEGER NOT NULL);
            INSERT INTO settings VALUES ('daily_target_mode', 'giveback', 1);
            INSERT INTO settings VALUES ('daily_giveback_pct', '25.0', 1);
            INSERT INTO settings VALUES ('daily_risk_pct', '5.0', 1);
            INSERT INTO settings VALUES ('max_positions', '5', 1);
            INSERT INTO settings VALUES ('risk_override_enabled', 'false', 1);
            INSERT INTO settings VALUES ('risk_per_trade_pct', '1.0', 1);
            """
        )
        handle_update_settings(conn, {"patch": {"daily_giveback_pct": 33.5}})
        result = handle_get_settings(conn, {})
        assert result["daily_giveback_pct"] == pytest.approx(33.5)

    def test_in_giveback_mode_profit_target_is_arm_point(self) -> None:
        # Semantic test: when daily_target_mode=giveback, daily_profit_target_pct
        # is documented as the arm threshold. Verify the circuit breaker honours it.
        state = _state(2_000.0)
        cfg = ExecutionConfig(
            daily_target_mode="giveback",
            daily_profit_target_pct=10.0,
            daily_giveback_pct=25.0,
        )
        # Just below arm point → not armed, no halt
        action = _call(state, realized=199.0, unrealized=0.0, cfg=cfg)
        assert action == DailyAction.NONE
        assert not state.giveback_armed

        # At arm point → armed, no halt
        action = _call(state, realized=200.0, unrealized=0.0, cfg=cfg)
        assert action == DailyAction.NONE
        assert state.giveback_armed
