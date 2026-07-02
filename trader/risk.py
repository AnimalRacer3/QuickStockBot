"""Risk engine: pure math for position sizing, exit levels, and the account-level
circuit breakers (kill-switch, profit-giveback, no-trade cutoff).

Every function here is deterministic and side-effect free so it can be unit
tested without a broker or market connection.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime

from trader.models import Candle, ExitReason, Position


def position_size(
    equity: float,
    buying_power: float,
    price: float,
    risk_per_trade_pct: float,
    stop_loss_pct: float,
    max_position_pct_bp: float,
) -> int:
    """Whole shares to buy, respecting both the per-trade risk cap and the
    max-position-as-%-of-buying-power cap. Returns 0 if inputs don't allow a trade."""
    if price <= 0 or equity <= 0 or buying_power <= 0:
        return 0

    risk_amount = equity * (risk_per_trade_pct / 100.0)
    risk_per_share = price * (stop_loss_pct / 100.0)
    if risk_per_share <= 0:
        return 0
    qty_by_risk = risk_amount / risk_per_share

    max_position_value = buying_power * (max_position_pct_bp / 100.0)
    qty_by_position_cap = max_position_value / price

    qty = math.floor(min(qty_by_risk, qty_by_position_cap))
    return max(qty, 0)


def stop_price(entry_price: float, stop_loss_pct: float) -> float:
    return entry_price * (1 - stop_loss_pct / 100.0)


def target_price(entry_price: float, take_profit_pct: float) -> float:
    return entry_price * (1 + take_profit_pct / 100.0)


def trail_off_trigger_price(entry_price: float, trail_off_trigger_pct: float) -> float:
    return entry_price * (1 + trail_off_trigger_pct / 100.0)


def next_scale_out_pct(current_scaled_out_pct: float, trail_off_scale_out_pct: float) -> float:
    return min(100.0, current_scaled_out_pct + trail_off_scale_out_pct)


def kill_switch_triggered(starting_equity: float, current_equity: float, daily_kill_switch_pct: float) -> bool:
    """`daily_kill_switch_pct` is negative (e.g. -10). Triggers once equity has
    dropped by at least that percent from the day's starting equity."""
    if starting_equity <= 0:
        return False
    pct_change = (current_equity - starting_equity) / starting_equity * 100.0
    return pct_change <= daily_kill_switch_pct


def profit_giveback_triggered(
    starting_equity: float, green_peak_equity: float, current_equity: float, daily_profit_giveback_pct: float
) -> bool:
    """Stops new entries once the account has given back `daily_profit_giveback_pct`
    of its peak gain-above-starting-equity for the day. No-ops on a day that never
    went green (peak <= starting)."""
    gain_at_peak = green_peak_equity - starting_equity
    if gain_at_peak <= 0:
        return False
    given_back = green_peak_equity - current_equity
    if given_back <= 0:
        return False
    giveback_pct = given_back / gain_at_peak * 100.0
    return giveback_pct >= daily_profit_giveback_pct


def no_trade_cutoff_triggered(now: datetime, market_open: datetime, no_trade_cutoff_hours: float, entries_made: int) -> bool:
    if entries_made > 0:
        return False
    elapsed_hours = (now - market_open).total_seconds() / 3600.0
    return elapsed_hours >= no_trade_cutoff_hours


@dataclass(frozen=True)
class RiskConfig:
    stop_loss_pct: float
    take_profit_pct: float
    trail_off_trigger_pct: float
    trail_off_scale_out_pct: float
    overextension_pct: float


def evaluate_exit(
    position: Position,
    candle: Candle,
    vwap_value: float,
    volume_confirmed_on_candle: bool,
    cfg: RiskConfig,
) -> tuple[ExitReason | None, float]:
    """Evaluate exit priority order on one completed candle: take-profit, then
    stop-loss, then trail-off scale-out, then VWAP-loss-with-volume.

    Returns (reason, scale_out_pct_of_remaining) -- scale_out_pct is 100 for a
    full exit (take-profit, stop-loss, VWAP loss) or the configured partial
    trim amount for a trail-off step. Returns (None, 0.0) if nothing triggers.
    """
    target = target_price(position.entry_price, cfg.take_profit_pct)
    if candle.high >= target:
        return ExitReason.TAKE_PROFIT, 100.0

    stop = stop_price(position.entry_price, cfg.stop_loss_pct)
    if candle.low <= stop:
        return ExitReason.STOP_LOSS, 100.0

    trigger = trail_off_trigger_price(position.entry_price, cfg.trail_off_trigger_pct)
    if position.peak_price >= trigger and candle.is_red:
        return ExitReason.TRAIL_OFF, cfg.trail_off_scale_out_pct

    if candle.close < vwap_value and volume_confirmed_on_candle:
        return ExitReason.VWAP_LOSS, 100.0

    return None, 0.0
