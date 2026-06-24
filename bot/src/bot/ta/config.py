from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TAConfig:
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    macd_slope_lookback: int = 3
    macd_enforce_above_zero: bool = True
    pattern_candle_lookback: int = 5
    enabled_patterns: list[str] = field(
        default_factory=lambda: [
            "bullish_engulfing",
            "hammer",
            "morning_star",
            "bullish_continuation",
        ]
    )
