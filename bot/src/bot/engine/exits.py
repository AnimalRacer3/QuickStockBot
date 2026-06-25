from __future__ import annotations

import math
from dataclasses import dataclass, field

from bot.ta.models import MacdState


@dataclass
class OpenPosition:
    symbol: str
    entry_price: float
    shares: int
    remaining_shares: int
    high_water_mark: float  # for trailing stop
    pattern_tags: list[str] = field(default_factory=list)

    @property
    def is_closed(self) -> bool:
        return self.remaining_shares <= 0


@dataclass
class ExitSignal:
    symbol: str
    shares_to_sell: int
    reason: str
    is_final: bool  # True when position fully closed


def _is_bullish_state(macd: MacdState, pattern_tags: list[str], bullish_tags: set[str]) -> bool:
    """Return True when momentum stays bullish: MACD eligible + bullish pattern, no reversal."""
    from bot.engine.gate import _BEARISH_TAGS

    has_bullish = any(t in bullish_tags for t in pattern_tags)
    has_reversal = any(t in _BEARISH_TAGS for t in pattern_tags)
    return macd.eligible and has_bullish and not has_reversal


def check_take_profit(position: OpenPosition, current_price: float, take_profit_pct: float) -> bool:
    """Return True when price has reached the take-profit level."""
    target = position.entry_price * (1.0 + take_profit_pct / 100.0)
    return current_price >= target


def check_trailing_stop(
    position: OpenPosition, current_price: float, trailing_stop_pct: float
) -> bool:
    """Return True when price has fallen below the trailing stop from the high water mark."""
    stop_level = position.high_water_mark * (1.0 - trailing_stop_pct / 100.0)
    return current_price <= stop_level


def update_high_water_mark(position: OpenPosition, current_price: float) -> None:
    if current_price > position.high_water_mark:
        position.high_water_mark = current_price


def dump_exit(position: OpenPosition, reason: str) -> ExitSignal:
    """Market-sell the entire remaining position at once."""
    return ExitSignal(
        symbol=position.symbol,
        shares_to_sell=position.remaining_shares,
        reason=reason,
        is_final=True,
    )


def trail_off_per_candle(
    position: OpenPosition,
    macd: MacdState,
    pattern_tags: list[str],
    bullish_tags: set[str],
    fraction: float,
    reason: str = "",
) -> ExitSignal | None:
    """
    Scale out `fraction` of remaining shares each candle while bullish.
    Dump the remainder once bullishness ends.
    """
    still_bullish = _is_bullish_state(macd, pattern_tags, bullish_tags)

    if not still_bullish:
        return dump_exit(position, reason or "bullishness ended, dumping remainder")

    shares_to_sell = max(1, math.floor(position.remaining_shares * fraction))
    # Don't sell more than we have
    shares_to_sell = min(shares_to_sell, position.remaining_shares)
    is_final = shares_to_sell >= position.remaining_shares

    return ExitSignal(
        symbol=position.symbol,
        shares_to_sell=shares_to_sell,
        reason=reason or "trail_off per_candle scale-out",
        is_final=is_final,
    )


def trail_off_candle_pattern(
    position: OpenPosition,
    macd: MacdState,
    pattern_tags: list[str],
    bullish_tags: set[str],
    prev_pattern_tags: list[str],
    fraction: float,
    reason: str = "",
) -> ExitSignal | None:
    """
    Scale out each time a bullish pattern reconfirms (new pattern tag appears).
    Dump the remainder once bullishness ends.
    """
    still_bullish = _is_bullish_state(macd, pattern_tags, bullish_tags)

    if not still_bullish:
        return dump_exit(position, reason or "bullishness ended, dumping remainder")

    # Check if a new bullish pattern has appeared since last candle
    new_bullish = set(pattern_tags) - set(prev_pattern_tags)
    new_bullish_hits = new_bullish & bullish_tags
    if not new_bullish_hits:
        return None  # No new pattern confirmation, hold

    shares_to_sell = max(1, math.floor(position.remaining_shares * fraction))
    shares_to_sell = min(shares_to_sell, position.remaining_shares)
    is_final = shares_to_sell >= position.remaining_shares

    return ExitSignal(
        symbol=position.symbol,
        shares_to_sell=shares_to_sell,
        reason=reason or f"trail_off candle_pattern reconfirm: {new_bullish_hits}",
        is_final=is_final,
    )
