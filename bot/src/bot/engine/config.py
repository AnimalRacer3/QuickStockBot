from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class ExecutionConfig:
    # Scanner
    active_tickers_n: int = 10

    # Risk / sizing
    stop_loss_pct: float = 1.0
    take_profit_pct: float = 3.0
    daily_max_loss_pct: float = -2.0       # negative
    daily_profit_target_pct: float = 3.0   # positive
    position_size_pct: float = 25.0        # max position as % of buying power
    override_risk_per_trade: bool = False   # if True, use risk_per_trade_pct (must be < |daily_max_loss_pct|)
    risk_per_trade_pct: float = 1.0        # only effective when override_risk_per_trade=True

    # Circuit breakers
    flatten_on_max_loss: bool = True
    flatten_on_profit_target: bool = False

    # Exit mode
    exit_mode: Literal["dump", "trail_off"] = "dump"
    trail_off_trigger: Literal["per_candle", "candle_pattern"] = "per_candle"
    trail_off_fraction_per_candle: float = 0.25

    # Trailing stop (independent)
    trailing_stop: bool = False
    trailing_stop_pct: float = 1.0

    # Session controls
    force_close_at_close: bool = True
    z_hour_cutoff: float = 1.0

    # ML conviction gate (Section 7 stub)
    conviction_threshold: float = 0.6

    # Margin / PDT notice
    min_account_equity_notice: float = 2000.0

    # TA config passthrough
    enabled_patterns: list[str] = field(
        default_factory=lambda: [
            "bullish_engulfing",
            "hammer",
            "morning_star",
            "bullish_continuation",
        ]
    )

    # Overextension gate: skip if price > VWAP * (1 + overextension_pct/100)
    overextension_pct: float = 3.0

    def effective_risk_pct(self) -> float:
        """Return the per-trade risk % to use for sizing."""
        daily_abs = abs(self.daily_max_loss_pct)
        if self.override_risk_per_trade and self.risk_per_trade_pct < daily_abs:
            return self.risk_per_trade_pct
        return daily_abs

    def goalpost_trade_count(self) -> int:
        """Goal-post number of trades needed to hit daily max loss at effective sizing."""
        import math
        eff = self.effective_risk_pct()
        if eff <= 0:
            return 1
        return math.ceil(abs(self.daily_max_loss_pct) / eff)
