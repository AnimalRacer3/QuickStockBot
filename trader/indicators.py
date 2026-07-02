"""Pure technical-indicator functions: VWAP, MACD, RVOL, volume confirmation.

All functions take plain sequences of `Candle` (or floats) and return plain
values -- no I/O, no config, no side effects -- so they're trivially unit
testable and reusable from both the live engine and --replay.
"""

from __future__ import annotations

from trader.models import Candle


def vwap(candles: list[Candle]) -> float:
    """Session-cumulative volume-weighted average price over the given candles."""
    if not candles:
        return 0.0
    total_pv = 0.0
    total_vol = 0.0
    for c in candles:
        typical_price = (c.high + c.low + c.close) / 3.0
        total_pv += typical_price * c.volume
        total_vol += c.volume
    if total_vol == 0:
        return candles[-1].close
    return total_pv / total_vol


def ema(values: list[float], period: int) -> list[float]:
    """Standard exponential moving average, seeded with a simple average."""
    if len(values) < period:
        return []
    multiplier = 2.0 / (period + 1)
    result = [sum(values[:period]) / period]
    for value in values[period:]:
        result.append((value - result[-1]) * multiplier + result[-1])
    return result


def macd(
    closes: list[float], fast: int = 12, slow: int = 26, signal: int = 9
) -> tuple[list[float], list[float], list[float]]:
    """Return (macd_line, signal_line, histogram), aligned to the tail of `closes`.

    Returns empty lists if there isn't enough data for a stable slow EMA.
    """
    if len(closes) < slow + signal:
        return [], [], []

    fast_ema = ema(closes, fast)
    slow_ema = ema(closes, slow)
    # Align: fast_ema is longer (starts earlier) than slow_ema by (slow - fast) points.
    offset = len(fast_ema) - len(slow_ema)
    fast_aligned = fast_ema[offset:]
    macd_line = [f - s for f, s in zip(fast_aligned, slow_ema)]

    signal_line = ema(macd_line, signal)
    macd_offset = len(macd_line) - len(signal_line)
    macd_aligned = macd_line[macd_offset:]
    histogram = [m - s for m, s in zip(macd_aligned, signal_line)]

    return macd_aligned, signal_line, histogram


def macd_is_bullish(
    closes: list[float],
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
    mode: str = "positive_or_rising",
    slope_lookback: int = 3,
) -> bool:
    """True if MACD histogram is positive, or (in positive_or_rising mode) rising."""
    macd_line, signal_line, histogram = macd(closes, fast, slow, signal)
    if not histogram:
        return False

    current = histogram[-1]
    if current > 0:
        return True
    if mode != "positive_or_rising":
        return False

    lookback = histogram[-slope_lookback:] if len(histogram) >= slope_lookback else histogram
    if len(lookback) < 2:
        return False
    return all(b > a for a, b in zip(lookback, lookback[1:]))


def relative_volume(current_volume: float, average_volume: float) -> float:
    """RVOL = current period volume / historical average volume for the same period."""
    if average_volume <= 0:
        return 0.0
    return current_volume / average_volume


def volume_confirmed(trigger_candle: Candle, prior_candles: list[Candle], multiplier: float = 1.5) -> bool:
    """True if the trigger candle's volume is >= multiplier x the average of the prior N candles."""
    if not prior_candles:
        return False
    avg_prior_volume = sum(c.volume for c in prior_candles) / len(prior_candles)
    if avg_prior_volume <= 0:
        return trigger_candle.volume > 0
    return trigger_candle.volume >= multiplier * avg_prior_volume


def pct_above_vwap(price: float, vwap_value: float) -> float:
    """Percent by which `price` is above `vwap_value` (negative if below)."""
    if vwap_value <= 0:
        return 0.0
    return (price - vwap_value) / vwap_value * 100.0
