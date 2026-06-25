"""Circuit breaker tests — Section 6."""

from __future__ import annotations

from bot.engine.circuit_breaker import DailyAction, DailyState, check_daily_limits
from bot.engine.config import ExecutionConfig


def _state(equity: float = 100_000.0) -> DailyState:
    return DailyState(day_start_equity=equity)


def _cfg(**kwargs: object) -> ExecutionConfig:
    return ExecutionConfig(**kwargs)  # type: ignore[arg-type]


class TestMaxLoss:
    def test_below_threshold_flatten_and_halt(self) -> None:
        cfg = _cfg(daily_max_loss_pct=-2.0, flatten_on_max_loss=True)
        state = _state(100_000)
        action = check_daily_limits(state, realized_pnl=-2100.0, unrealized_pnl=0.0, config=cfg)
        assert action == DailyAction.FLATTEN_AND_HALT
        assert state.halted

    def test_below_threshold_halt_only(self) -> None:
        cfg = _cfg(daily_max_loss_pct=-2.0, flatten_on_max_loss=False)
        state = _state(100_000)
        action = check_daily_limits(state, realized_pnl=-2100.0, unrealized_pnl=0.0, config=cfg)
        assert action == DailyAction.HALT
        assert state.halted

    def test_exactly_at_threshold_halts(self) -> None:
        cfg = _cfg(daily_max_loss_pct=-2.0, flatten_on_max_loss=True)
        state = _state(100_000)
        action = check_daily_limits(state, realized_pnl=-2000.0, unrealized_pnl=0.0, config=cfg)
        assert action == DailyAction.FLATTEN_AND_HALT

    def test_above_threshold_continues(self) -> None:
        cfg = _cfg(daily_max_loss_pct=-2.0)
        state = _state(100_000)
        action = check_daily_limits(state, realized_pnl=-1000.0, unrealized_pnl=0.0, config=cfg)
        assert action == DailyAction.NONE
        assert not state.halted

    def test_combined_pnl_triggers(self) -> None:
        # realized=-1000, unrealized=-1200 → total=-2200 → -2.2%
        cfg = _cfg(daily_max_loss_pct=-2.0, flatten_on_max_loss=True)
        state = _state(100_000)
        action = check_daily_limits(state, realized_pnl=-1000.0, unrealized_pnl=-1200.0, config=cfg)
        assert action == DailyAction.FLATTEN_AND_HALT

    def test_already_halted_returns_halt(self) -> None:
        cfg = _cfg(daily_max_loss_pct=-2.0)
        state = _state(100_000)
        state.halted = True
        state.halt_reason = "previous halt"
        action = check_daily_limits(state, realized_pnl=0.0, unrealized_pnl=0.0, config=cfg)
        assert action == DailyAction.HALT


class TestProfitTarget:
    def test_reaches_target_flatten_and_halt(self) -> None:
        cfg = _cfg(daily_profit_target_pct=3.0, flatten_on_profit_target=True)
        state = _state(100_000)
        action = check_daily_limits(state, realized_pnl=3100.0, unrealized_pnl=0.0, config=cfg)
        assert action == DailyAction.FLATTEN_AND_HALT

    def test_reaches_target_halt_only(self) -> None:
        cfg = _cfg(daily_profit_target_pct=3.0, flatten_on_profit_target=False)
        state = _state(100_000)
        action = check_daily_limits(state, realized_pnl=3100.0, unrealized_pnl=0.0, config=cfg)
        assert action == DailyAction.HALT
        assert state.halted

    def test_exactly_at_target_halts(self) -> None:
        cfg = _cfg(daily_profit_target_pct=3.0, flatten_on_profit_target=True)
        state = _state(100_000)
        action = check_daily_limits(state, realized_pnl=3000.0, unrealized_pnl=0.0, config=cfg)
        assert action == DailyAction.FLATTEN_AND_HALT

    def test_below_target_continues(self) -> None:
        cfg = _cfg(daily_profit_target_pct=3.0, flatten_on_profit_target=True)
        state = _state(100_000)
        action = check_daily_limits(state, realized_pnl=2500.0, unrealized_pnl=0.0, config=cfg)
        assert action == DailyAction.NONE

    def test_single_trade_can_hit_target(self) -> None:
        # Core of the "prefer 1 trade" incentive
        cfg = _cfg(
            daily_profit_target_pct=3.0,
            flatten_on_profit_target=False,
            daily_max_loss_pct=-2.0,
        )
        state = _state(100_000)
        action = check_daily_limits(state, realized_pnl=3500.0, unrealized_pnl=0.0, config=cfg)
        assert action == DailyAction.HALT
        assert state.halted
