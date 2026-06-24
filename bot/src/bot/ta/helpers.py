from __future__ import annotations

from bot.models import Bar


def high_of_day(bars: list[Bar]) -> float:
    return float(max(bar.high for bar in bars))


def low_of_day(bars: list[Bar]) -> float:
    return float(min(bar.low for bar in bars))


def current_price(bar: Bar) -> float:
    return float(bar.close)


def vwap(bars: list[Bar]) -> float:
    """Volume-weighted average price over the supplied bars."""
    total_volume = sum(bar.volume for bar in bars)
    if total_volume == 0:
        return float(bars[-1].close)
    total_pv = sum(
        ((float(bar.high) + float(bar.low) + float(bar.close)) / 3.0) * bar.volume
        for bar in bars
    )
    return total_pv / total_volume
