from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from bot.engine.config import ExecutionConfig


class DailyAction(str, Enum):
    NONE = "none"
    HALT = "halt"
    FLATTEN_AND_HALT = "flatten_and_halt"


@dataclass
class DailyState:
    """Tracks intraday P/L relative to equity at day start."""

    day_start_equity: float
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    halted: bool = False
    halt_reason: str = ""
    # Expose goalpost so the learning model (Section 7) can target it.
    goalpost_trade_count: int = 1

    @property
    def total_pnl(self) -> float:
        return self.realized_pnl + self.unrealized_pnl

    @property
    def total_pnl_pct(self) -> float:
        if self.day_start_equity <= 0:
            return 0.0
        return (self.total_pnl / self.day_start_equity) * 100.0


def check_daily_limits(
    state: DailyState,
    realized_pnl: float,
    unrealized_pnl: float,
    config: ExecutionConfig,
) -> DailyAction:
    """
    Evaluate circuit breakers with updated P/L figures.

    Updates state in-place. Returns the action to take:
      - NONE               → continue normally
      - HALT               → stop new entries, keep existing positions
      - FLATTEN_AND_HALT   → close all positions and stop entries
    """
    state.realized_pnl = realized_pnl
    state.unrealized_pnl = unrealized_pnl

    if state.halted:
        return DailyAction.HALT

    pnl_pct = state.total_pnl_pct

    # Max-loss circuit breaker (daily_max_loss_pct is negative)
    if pnl_pct <= config.daily_max_loss_pct:
        state.halted = True
        state.halt_reason = (
            f"daily max loss hit ({pnl_pct:.2f}% <= {config.daily_max_loss_pct:.2f}%)"
        )
        if config.flatten_on_max_loss:
            return DailyAction.FLATTEN_AND_HALT
        return DailyAction.HALT

    # Profit-target circuit breaker
    if pnl_pct >= config.daily_profit_target_pct:
        state.halted = True
        state.halt_reason = f"daily profit target hit ({pnl_pct:.2f}% >= {config.daily_profit_target_pct:.2f}%)"
        if config.flatten_on_profit_target:
            return DailyAction.FLATTEN_AND_HALT
        return DailyAction.HALT

    return DailyAction.NONE
