from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal

from bot.engine.config import ExecutionConfig


@dataclass
class SizingResult:
    shares: int
    effective_risk_pct: float
    per_share_risk: float
    max_risk_dollars: float
    position_value: float
    skipped: bool
    skip_reason: str = ""


def compute_shares(
    equity: float,
    buying_power: float,
    entry_price: float,
    config: ExecutionConfig,
) -> SizingResult:
    """
    Greyed/risk-based sizing per Section 6 spec.

    Effective risk = |daily_max_loss_pct| by default.
    If override_risk_per_trade=True AND configured value < daily abs, use it.
    Overrides >= daily number are rejected (fall back to daily number).
    """
    daily_abs = abs(config.daily_max_loss_pct)

    if config.override_risk_per_trade:
        if config.risk_per_trade_pct >= daily_abs:
            # Override rejected: value >= daily number
            eff_risk_pct = daily_abs
        else:
            eff_risk_pct = config.risk_per_trade_pct
    else:
        eff_risk_pct = daily_abs

    per_share_risk = entry_price * (config.stop_loss_pct / 100.0)
    if per_share_risk <= 0:
        return SizingResult(
            shares=0,
            effective_risk_pct=eff_risk_pct,
            per_share_risk=per_share_risk,
            max_risk_dollars=0.0,
            position_value=0.0,
            skipped=True,
            skip_reason="per_share_risk <= 0",
        )

    max_risk_dollars = equity * (eff_risk_pct / 100.0)
    raw_shares = max_risk_dollars / per_share_risk
    shares = math.floor(raw_shares)

    if shares < 1:
        return SizingResult(
            shares=0,
            effective_risk_pct=eff_risk_pct,
            per_share_risk=per_share_risk,
            max_risk_dollars=max_risk_dollars,
            position_value=0.0,
            skipped=True,
            skip_reason="shares < 1",
        )

    # Cap: shares * entry <= buying_power * position_size_pct
    bp_cap_value = buying_power * (config.position_size_pct / 100.0)
    bp_cap_shares = math.floor(bp_cap_value / entry_price)

    # Cap: shares * entry <= available buying_power
    avail_cap_shares = math.floor(buying_power / entry_price)

    shares = min(shares, bp_cap_shares, avail_cap_shares)

    if shares < 1:
        return SizingResult(
            shares=0,
            effective_risk_pct=eff_risk_pct,
            per_share_risk=per_share_risk,
            max_risk_dollars=max_risk_dollars,
            position_value=0.0,
            skipped=True,
            skip_reason="shares < 1 after buying_power cap",
        )

    position_value = shares * entry_price
    return SizingResult(
        shares=shares,
        effective_risk_pct=eff_risk_pct,
        per_share_risk=per_share_risk,
        max_risk_dollars=max_risk_dollars,
        position_value=position_value,
        skipped=False,
    )
