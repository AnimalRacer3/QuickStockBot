"""
Settings override enforcement tests.

Rules:
  override OFF → risk_per_trade_pct locked to daily_risk_pct / max_positions;
                 any patch value for risk_per_trade_pct is silently ignored.
  override ON  → risk_per_trade_pct may be set explicitly but must be
                 strictly less than daily_risk_pct (>=daily is rejected).
  goal_post    → always returned; equals floor(daily / effective_per_trade).
"""

from __future__ import annotations

import pytest

from bot.control.connection import DbConn
from bot.control.handlers import handle_get_settings, handle_update_settings

# ─── Helper ───────────────────────────────────────────────────────────────────


def _set(conn: DbConn, **kv: object) -> dict:
    return handle_update_settings(conn, {"patch": dict(kv)})


def _get(conn: DbConn) -> dict:
    return handle_get_settings(conn, {})


# ─── Override OFF (default) ───────────────────────────────────────────────────


class TestOverrideOff:
    def test_default_override_is_false(self, db: DbConn) -> None:
        settings = _get(db)
        assert settings["risk_override_enabled"] is False

    def test_locked_value_equals_daily_over_max(self, db: DbConn) -> None:
        _set(db, daily_risk_pct=10.0, max_positions=5)
        settings = _get(db)
        assert settings["risk_per_trade_pct"] == pytest.approx(10.0 / 5)

    def test_patch_per_trade_ignored_when_override_off(
        self, db: DbConn
    ) -> None:
        _set(db, daily_risk_pct=10.0, max_positions=5)
        # Try to set per-trade to 99 — should be silently ignored
        result = _set(db, risk_per_trade_pct=99.0)
        assert result["risk_per_trade_pct"] == pytest.approx(10.0 / 5)

    def test_goal_post_equals_max_positions_when_override_off(
        self, db: DbConn
    ) -> None:
        _set(db, daily_risk_pct=6.0, max_positions=3)
        settings = _get(db)
        # effective_per_trade = 6/3 = 2; goal_post = floor(6/2) = 3 = max_positions
        assert settings["goal_post_trade_count"] == 3


# ─── Override ON ─────────────────────────────────────────────────────────────


class TestOverrideOn:
    def test_can_set_per_trade_when_override_on(self, db: DbConn) -> None:
        _set(
            db, risk_override_enabled=True, daily_risk_pct=10.0, risk_per_trade_pct=2.0
        )
        settings = _get(db)
        assert settings["risk_override_enabled"] is True
        assert settings["risk_per_trade_pct"] == pytest.approx(2.0)

    def test_rejects_per_trade_equal_to_daily(self, db: DbConn) -> None:
        _set(db, risk_override_enabled=True, daily_risk_pct=5.0)
        with pytest.raises(ValueError, match="strictly less than"):
            _set(db, risk_per_trade_pct=5.0)

    def test_rejects_per_trade_greater_than_daily(self, db: DbConn) -> None:
        _set(db, risk_override_enabled=True, daily_risk_pct=5.0)
        with pytest.raises(ValueError, match="strictly less than"):
            _set(db, risk_per_trade_pct=6.0)

    def test_accepts_per_trade_below_daily(self, db: DbConn) -> None:
        _set(db, risk_override_enabled=True, daily_risk_pct=5.0, risk_per_trade_pct=1.5)
        settings = _get(db)
        assert settings["risk_per_trade_pct"] == pytest.approx(1.5)

    def test_goal_post_computed_from_override_value(
        self, db: DbConn
    ) -> None:
        _set(db, risk_override_enabled=True, daily_risk_pct=9.0, risk_per_trade_pct=3.0)
        settings = _get(db)
        assert settings["goal_post_trade_count"] == 3  # floor(9/3)

    def test_goal_post_is_always_at_least_one(self, db: DbConn) -> None:
        # Per-trade just barely below daily → goal_post = 1
        _set(db, risk_override_enabled=True, daily_risk_pct=5.0, risk_per_trade_pct=4.9)
        settings = _get(db)
        assert settings["goal_post_trade_count"] >= 1


# ─── Turning override on/off mid-session ─────────────────────────────────────


class TestOverrideToggle:
    def test_disable_override_locks_per_trade(self, db: DbConn) -> None:
        # Enable override and set a custom value
        _set(
            db, risk_override_enabled=True, daily_risk_pct=10.0, risk_per_trade_pct=3.0
        )
        # Disable override
        _set(db, risk_override_enabled=False)
        settings = _get(db)
        # Should now return locked value = 10/5 = 2.0 (max_positions=5 by default)
        assert settings["risk_per_trade_pct"] == pytest.approx(10.0 / 5)

    def test_enable_override_then_reject_equal(self, db: DbConn) -> None:
        _set(db, daily_risk_pct=8.0)
        with pytest.raises(ValueError):
            _set(db, risk_override_enabled=True, risk_per_trade_pct=8.0)
