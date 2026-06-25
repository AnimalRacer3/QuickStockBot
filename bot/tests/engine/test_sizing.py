"""Position sizing tests — Section 6."""

from __future__ import annotations

import pytest

from bot.engine.config import ExecutionConfig
from bot.engine.sizing import compute_shares


def _cfg(**kwargs: object) -> ExecutionConfig:
    return ExecutionConfig(**kwargs)  # type: ignore[arg-type]


class TestDefaultSizing:
    """Greyed default: effective_risk_pct = |daily_max_loss_pct|."""

    def test_effective_risk_equals_daily_abs_by_default(self) -> None:
        cfg = _cfg(daily_max_loss_pct=-2.0, stop_loss_pct=1.0)
        result = compute_shares(100_000, 100_000, 100.0, cfg)
        assert result.effective_risk_pct == 2.0
        assert not result.skipped

    def test_shares_math(self) -> None:
        # equity=100_000, risk_pct=2.0%, max_risk=$2000, stop_loss=1%, per_share_risk=$1
        # shares = floor(2000 / 1) = 2000
        cfg = _cfg(daily_max_loss_pct=-2.0, stop_loss_pct=1.0, position_size_pct=100.0)
        result = compute_shares(100_000, 200_000, 100.0, cfg)
        assert result.shares == 2000
        assert result.max_risk_dollars == pytest.approx(2000.0)
        assert result.per_share_risk == pytest.approx(1.0)

    def test_goalpost_default(self) -> None:
        cfg = _cfg(daily_max_loss_pct=-2.0, override_risk_per_trade=False)
        # effective = 2.0, daily = 2.0, goalpost = ceil(2/2) = 1
        assert cfg.goalpost_trade_count() == 1

    def test_goalpost_fractional(self) -> None:
        cfg = _cfg(
            daily_max_loss_pct=-3.0,
            override_risk_per_trade=True,
            risk_per_trade_pct=1.0,
        )
        # effective = 1.0, daily = 3.0, goalpost = ceil(3/1) = 3
        assert cfg.goalpost_trade_count() == 3


class TestOverrideSizing:
    """Override risk_per_trade_pct — must be < |daily_max_loss_pct|."""

    def test_valid_lower_override_accepted(self) -> None:
        cfg = _cfg(
            daily_max_loss_pct=-2.0,
            override_risk_per_trade=True,
            risk_per_trade_pct=0.5,
        )
        result = compute_shares(100_000, 200_000, 100.0, cfg)
        assert result.effective_risk_pct == 0.5

    def test_override_equal_to_daily_rejected(self) -> None:
        cfg = _cfg(
            daily_max_loss_pct=-2.0,
            override_risk_per_trade=True,
            risk_per_trade_pct=2.0,  # equal — rejected
        )
        result = compute_shares(100_000, 200_000, 100.0, cfg)
        assert result.effective_risk_pct == 2.0  # fell back to daily

    def test_override_greater_than_daily_rejected(self) -> None:
        cfg = _cfg(
            daily_max_loss_pct=-2.0,
            override_risk_per_trade=True,
            risk_per_trade_pct=3.0,  # > daily — rejected
        )
        result = compute_shares(100_000, 200_000, 100.0, cfg)
        assert result.effective_risk_pct == 2.0  # fell back to daily


class TestBuyingPowerCap:
    def test_capped_by_position_size_pct(self) -> None:
        # buying_power=10_000, position_size_pct=10% → max position = $1000
        # at price=100 → cap=10 shares
        cfg = _cfg(
            daily_max_loss_pct=-5.0,
            stop_loss_pct=0.1,  # tiny stop = huge raw shares
            position_size_pct=10.0,
        )
        result = compute_shares(100_000, 10_000, 100.0, cfg)
        assert result.shares <= 10
        assert not result.skipped

    def test_capped_by_available_buying_power(self) -> None:
        # buying_power=500, price=100 → at most 5 shares
        cfg = _cfg(
            daily_max_loss_pct=-5.0,
            stop_loss_pct=0.1,
            position_size_pct=100.0,
        )
        result = compute_shares(100_000, 500, 100.0, cfg)
        assert result.shares <= 5

    def test_shares_less_than_1_skipped(self) -> None:
        # tiny equity → max_risk too small to buy even 1 share
        cfg = _cfg(daily_max_loss_pct=-0.001, stop_loss_pct=1.0)
        result = compute_shares(100, 10_000, 100.0, cfg)
        assert result.skipped
        assert result.shares == 0

    def test_buying_power_too_low_skipped(self) -> None:
        cfg = _cfg(daily_max_loss_pct=-2.0, stop_loss_pct=1.0, position_size_pct=100.0)
        result = compute_shares(100_000, 0.50, 100.0, cfg)
        assert result.skipped
