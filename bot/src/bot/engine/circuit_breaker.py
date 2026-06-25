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
    # Giveback mode state (Section 18)
    daily_pl_high: float = 0.0  # running max of total_pnl over the day (dollars)
    giveback_armed: bool = False  # true once daily_pl_pct >= daily_profit_target_pct

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

    # Profit-side circuit breaker — behaviour depends on mode
    if config.daily_target_mode == "stop":
        # Legacy hard-stop: halt (and optionally flatten) the moment target is hit.
        if pnl_pct >= config.daily_profit_target_pct:
            state.halted = True
            state.halt_reason = (
                f"daily profit target hit ({pnl_pct:.2f}% >= "
                f"{config.daily_profit_target_pct:.2f}%)"
            )
            if config.flatten_on_profit_target:
                return DailyAction.FLATTEN_AND_HALT
            return DailyAction.HALT
    else:
        # Giveback mode: arm at activation threshold, then trail the high-water mark.
        # Always update the running high-water mark.
        current_pnl = state.total_pnl
        if current_pnl > state.daily_pl_high:
            state.daily_pl_high = current_pnl

        # Arm once the activation threshold is crossed.
        if not state.giveback_armed and pnl_pct >= config.daily_profit_target_pct:
            state.giveback_armed = True

        # If armed, check whether P/L has given back enough from the peak.
        if state.giveback_armed:
            trigger = state.daily_pl_high * (1.0 - config.daily_giveback_pct / 100.0)
            if current_pnl <= trigger:
                state.halted = True
                state.halt_reason = (
                    f"giveback triggered: daily_pl ${current_pnl:.2f} <= "
                    f"trigger ${trigger:.2f} "
                    f"(peak ${state.daily_pl_high:.2f}, "
                    f"giveback {config.daily_giveback_pct:.1f}%)"
                )
                return DailyAction.FLATTEN_AND_HALT

    return DailyAction.NONE
