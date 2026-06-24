from __future__ import annotations

import math

from bot.models import Bar
from bot.ta.config import TAConfig
from bot.ta.models import MacdState


def _ema(values: list[float], period: int) -> list[float]:
    """Exponential moving average; first value is the SMA seed."""
    if len(values) < period:
        return []
    alpha = 2.0 / (period + 1)
    result = [sum(values[:period]) / period]
    for v in values[period:]:
        result.append(alpha * v + (1.0 - alpha) * result[-1])
    return result


def compute_macd(
    prices: list[float],
    fast: int,
    slow: int,
    signal: int,
) -> tuple[list[float], list[float], list[float]]:
    """
    Returns (macd_line, signal_line, histogram) aligned to the shortest series.

    Minimum prices required: slow + signal - 1.
    """
    ema_fast = _ema(prices, fast)
    ema_slow = _ema(prices, slow)
    if not ema_fast or not ema_slow:
        return [], [], []

    # ema_fast[k] is at price index (fast-1+k).
    # ema_slow[k] is at price index (slow-1+k).
    # Align fast to slow: offset = slow - fast.
    offset = slow - fast
    macd_line = [ema_fast[k + offset] - ema_slow[k] for k in range(len(ema_slow))]

    sig_line = _ema(macd_line, signal)
    if not sig_line:
        return [], [], []

    # Align macd_line to sig_line (sig_line is shorter).
    macd_aligned = macd_line[len(macd_line) - len(sig_line) :]
    histogram = [m - s for m, s in zip(macd_aligned, sig_line)]
    return macd_aligned, sig_line, histogram


def compute_slope(values: list[float], lookback: int) -> float:
    """Linear-regression slope over the last `lookback` values."""
    if lookback < 2 or len(values) < lookback:
        return 0.0
    y = values[-lookback:]
    n = len(y)
    x_mean = (n - 1) / 2.0
    y_mean = sum(y) / n
    num = sum((i - x_mean) * (yi - y_mean) for i, yi in enumerate(y))
    den = sum((i - x_mean) ** 2 for i in range(n))
    return num / den if den else 0.0


def _favorability_enforce_on(slope: float, hist: float, value: float) -> float:
    """
    Favorability when enforce_above_zero=True.

    Eligible states (value > 0, slope >= 0) score in [0, 1], scaled by slope
    rate and histogram momentum.  All ineligible states return -1.0.
    """
    if value <= 0 or slope < 0:
        return -1.0
    ref = abs(value) if abs(value) > 1e-10 else 1e-10
    slope_rate = math.tanh(slope / ref * 5.0)  # [0, 1) since slope >= 0
    hist_adj = 0.2 if hist > 0 else (-0.1 if hist < 0 else 0.0)
    return max(0.0, min(1.0, 0.4 + 0.4 * slope_rate + hist_adj))


def _favorability_full(slope: float, hist: float, value: float) -> float:
    """
    Full favorability model (enforce_above_zero=False).

    Quadrant rules:
      Q1 value > 0, slope > 0  → strongly favorable  [ 0.4, 1.0]
      Q2 value > 0, slope <= 0 → unfavorable          [-1.0, -0.2]
      Q3 value <= 0, slope > 0 → moderately favorable (0.0, 0.4]
      Q4 value <= 0, slope <= 0→ unfavorable          [-1.0, -0.4]
    """
    ref = abs(value) if abs(value) > 1e-10 else 1e-10
    norm_slope = math.tanh(abs(slope) / ref * 5.0)  # [0, 1)
    hist_adj = math.tanh(hist / ref * 3.0) * 0.1  # small modifier in (-0.1, 0.1)

    above = value > 0
    rising = slope > 1e-10  # treat near-zero slope (floating-point noise) as flat

    if above and rising:
        return min(1.0, 0.5 + 0.4 * norm_slope + hist_adj)
    if above and not rising:
        # Flat (slope=0) → ≈ -0.2; steep downtrend → towards -1.0
        return max(-1.0, -0.2 - 0.6 * norm_slope + hist_adj)
    if not above and rising:
        # Below zero but rising: cap at 0.4
        return min(0.4, 0.1 + 0.3 * norm_slope + hist_adj)
    # Below zero and not rising
    return max(-1.0, -0.4 - 0.5 * norm_slope + hist_adj)


def classify_macd(bars: list[Bar], config: TAConfig) -> MacdState:
    """
    Compute MACD from closing prices and classify the state.

    Returns MacdState with value (MACD line), slope, hist, favorability ∈ [-1,1],
    and eligible flag.
    """
    prices = [float(b.close) for b in bars]
    macd_line, sig_line, histogram = compute_macd(
        prices, config.macd_fast, config.macd_slow, config.macd_signal
    )

    if not macd_line:
        return MacdState(
            value=0.0, slope=0.0, hist=0.0, favorability=-1.0, eligible=False
        )

    value = macd_line[-1]
    hist_val = histogram[-1]
    slope = compute_slope(macd_line, config.macd_slope_lookback)

    if config.macd_enforce_above_zero:
        favor = _favorability_enforce_on(slope, hist_val, value)
        eligible = value > 0 and slope >= 0
    else:
        favor = _favorability_full(slope, hist_val, value)
        eligible = favor > 0

    return MacdState(
        value=value,
        slope=slope,
        hist=hist_val,
        favorability=round(favor, 6),
        eligible=eligible,
    )
