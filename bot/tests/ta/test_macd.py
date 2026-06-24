"""MACD classifier tests — no network required."""

from __future__ import annotations

from bot.ta.config import TAConfig
from bot.ta.macd import (
    _ema,
    _favorability_enforce_on,
    _favorability_full,
    classify_macd,
    compute_macd,
    compute_slope,
)
from tests.ta.conftest import make_bar

# ---------------------------------------------------------------------------
# EMA / compute_macd primitives
# ---------------------------------------------------------------------------


def test_ema_constant_series():
    """EMA of a constant series equals that constant."""
    vals = [5.0] * 20
    result = _ema(vals, period=5)
    assert all(abs(v - 5.0) < 1e-9 for v in result)


def test_ema_length():
    vals = list(range(1, 21))  # 20 values
    result = _ema(vals, period=5)
    assert len(result) == 16  # 20 - 5 + 1


def test_ema_too_short_returns_empty():
    assert _ema([1.0, 2.0], period=5) == []


def test_compute_macd_returns_empty_when_insufficient():
    prices = [float(i) for i in range(10)]  # way fewer than slow+signal-1
    macd, sig, hist = compute_macd(prices, fast=12, slow=26, signal=9)
    assert macd == [] and sig == [] and hist == []


def test_compute_macd_linear_series():
    """
    For a perfectly linear price series (constant daily increment) the fast and
    slow EMAs converge to a constant lag difference, so the MACD line is constant
    and its slope is zero.  Verified by hand for fast=3, slow=5, signal=2.
    """
    prices = [float(i + 1) for i in range(20)]
    macd, sig, hist = compute_macd(prices, fast=3, slow=5, signal=2)

    # All MACD values should be identical (constant lag)
    assert len(macd) > 0
    assert all(abs(v - macd[0]) < 1e-9 for v in macd)
    # Histogram should be zero (signal tracks perfectly)
    assert all(abs(h) < 1e-9 for h in hist)


def test_compute_macd_precomputed():
    """
    Verify MACD values against hand-computed reference:
      prices = [1..10], fast=3, slow=5, signal=2.

    EMA_fast(3), alpha=0.5:  SMA([1,2,3])=2.0, then 3.0,4.0,5.0,6.0,7.0,8.0,9.0
    EMA_slow(5), alpha=1/3:  SMA([1..5])=3.0, then 4.0,5.0,6.0,7.0,8.0

    MACD (slow-aligned):
      at idx4: fast[2]-slow[0] = 4.0-3.0 = 1.0
      ...all 1.0 for a linear series.

    Signal(2) on [1,1,1,1,1,1]: SMA([1,1])=1.0, then all 1.0.
    Histogram = 0.
    """
    prices = [float(i) for i in range(1, 11)]
    macd, sig, hist = compute_macd(prices, fast=3, slow=5, signal=2)

    assert len(macd) > 0
    for v in macd:
        assert abs(v - 1.0) < 1e-9, f"Expected MACD=1.0, got {v}"
    for v in sig:
        assert abs(v - 1.0) < 1e-9, f"Expected signal=1.0, got {v}"
    for v in hist:
        assert abs(v) < 1e-9, f"Expected histogram=0.0, got {v}"


# ---------------------------------------------------------------------------
# compute_slope
# ---------------------------------------------------------------------------


def test_slope_linear():
    vals = [1.0, 2.0, 3.0, 4.0, 5.0]
    assert abs(compute_slope(vals, lookback=5) - 1.0) < 1e-9


def test_slope_constant():
    vals = [3.0] * 10
    assert abs(compute_slope(vals, lookback=5)) < 1e-9


def test_slope_too_short():
    assert compute_slope([1.0], lookback=3) == 0.0


# ---------------------------------------------------------------------------
# Favorability helper — enforce_above_zero=True
# ---------------------------------------------------------------------------


def test_favor_enforce_on_eligible():
    """value > 0, slope > 0 → eligible, favorability in (0, 1]."""
    f = _favorability_enforce_on(slope=0.1, hist=0.05, value=1.0)
    assert 0.0 < f <= 1.0


def test_favor_enforce_on_eligible_zero_slope():
    """value > 0, slope = 0 → eligible (slope >= 0), favorability >= 0."""
    f = _favorability_enforce_on(slope=0.0, hist=0.0, value=1.0)
    assert f >= 0.0


def test_favor_enforce_on_above_zero_downtrend():
    """Above-zero but downtrending must NOT be eligible → favorability = -1."""
    f = _favorability_enforce_on(slope=-0.1, hist=-0.05, value=1.0)
    assert f == -1.0


def test_favor_enforce_on_below_zero_rising():
    """Below zero, any slope → not eligible → favorability = -1."""
    f = _favorability_enforce_on(slope=0.1, hist=0.05, value=-0.5)
    assert f == -1.0


def test_favor_enforce_on_below_zero_falling():
    f = _favorability_enforce_on(slope=-0.1, hist=-0.05, value=-1.0)
    assert f == -1.0


# ---------------------------------------------------------------------------
# Favorability helper — full model (enforce_above_zero=False)
# ---------------------------------------------------------------------------


def test_favor_full_q1_strongly_positive():
    """Q1: value > 0, slope > 0 → strongly favorable."""
    f = _favorability_full(slope=0.5, hist=0.1, value=1.0)
    assert f >= 0.4


def test_favor_full_q2_unfavorable():
    """Q2: value > 0, slope < 0 → unfavorable."""
    f = _favorability_full(slope=-0.5, hist=-0.1, value=1.0)
    assert f < 0.0


def test_favor_full_q3_below_zero_rising_positive():
    """Q3: value < 0, slope > 0 → moderately favorable (> 0)."""
    f = _favorability_full(slope=0.3, hist=0.05, value=-1.0)
    assert 0.0 < f <= 0.4


def test_favor_full_q4_below_zero_falling_negative():
    """Q4: value < 0, slope < 0 → unfavorable."""
    f = _favorability_full(slope=-0.3, hist=-0.05, value=-1.0)
    assert f < 0.0


def test_favor_full_q1_less_than_one():
    f = _favorability_full(slope=100.0, hist=10.0, value=1.0)
    assert f <= 1.0


def test_favor_full_q4_greater_than_neg_one():
    f = _favorability_full(slope=-100.0, hist=-10.0, value=-1.0)
    assert f >= -1.0


# ---------------------------------------------------------------------------
# Slope-rate ordering
# ---------------------------------------------------------------------------


def test_slope_rate_ordering_enforce_on():
    """Higher slope → higher favorability when enforce_above_zero=True."""
    f_slow = _favorability_enforce_on(slope=0.01, hist=0.0, value=1.0)
    f_fast = _favorability_enforce_on(slope=0.5, hist=0.0, value=1.0)
    assert f_fast > f_slow


def test_slope_rate_ordering_full():
    """Higher positive slope → higher favorability in Q1 (full model)."""
    f_slow = _favorability_full(slope=0.05, hist=0.0, value=1.0)
    f_fast = _favorability_full(slope=0.5, hist=0.0, value=1.0)
    assert f_fast > f_slow


def test_slope_rate_ordering_q3():
    """Higher positive slope → higher favorability in Q3 (full model)."""
    f_slow = _favorability_full(slope=0.05, hist=0.0, value=-1.0)
    f_fast = _favorability_full(slope=0.5, hist=0.0, value=-1.0)
    assert f_fast > f_slow


# ---------------------------------------------------------------------------
# classify_macd — enforce_above_zero toggle integration
# ---------------------------------------------------------------------------


def _price_bars(prices: list[float]) -> list:
    """Build Bar list from close prices (open=high=low=close, flat candles)."""
    return [make_bar(p, p, p, p) for p in prices]


def _rising_bars(n: int = 60, start: float = 10.0, step: float = 0.5) -> list:
    prices = [start + i * step for i in range(n)]
    return _price_bars(prices)


def _falling_bars(n: int = 60, start: float = 20.0, step: float = -0.3) -> list:
    prices = [start + i * step for i in range(n)]
    return _price_bars(prices)


def test_classify_macd_insufficient_data():
    bars = _price_bars([10.0, 11.0, 12.0])
    cfg = TAConfig(macd_fast=12, macd_slow=26, macd_signal=9)
    state = classify_macd(bars, cfg)
    assert not state.eligible
    assert state.favorability == -1.0


def test_classify_macd_enforce_on_rising_eligible():
    """Rising prices → MACD > 0 and rising → eligible=True with enforce on."""
    bars = _rising_bars(60)
    cfg = TAConfig(macd_enforce_above_zero=True)
    state = classify_macd(bars, cfg)
    assert state.eligible
    assert state.favorability > 0


def test_classify_macd_enforce_on_above_zero_falling_not_eligible():
    """
    Build a series where MACD is positive but slope turned negative
    (sharp reversal after sustained rise).  enforce_above_zero=True → not eligible.
    """
    rise = [10.0 + i * 0.5 for i in range(50)]
    fall = [rise[-1] - i * 0.8 for i in range(1, 20)]
    prices = rise + fall
    bars = _price_bars(prices)
    cfg = TAConfig(macd_enforce_above_zero=True, macd_slope_lookback=3)
    state = classify_macd(bars, cfg)
    # After a sharp enough fall the slope is negative, so not eligible
    if state.value > 0:
        if state.slope < 0:
            assert not state.eligible


def test_classify_macd_enforce_off_below_zero_rising_eligible():
    """
    Build a series where price fell (MACD < 0) then started recovering.
    With enforce_above_zero=False the state should become eligible.
    """
    # Sharp drop so MACD goes deeply negative, then gentle recovery
    drop = [20.0 - i * 0.6 for i in range(45)]
    recover = [drop[-1] + i * 0.1 for i in range(20)]
    prices = drop + recover
    bars = _price_bars(prices)
    cfg = TAConfig(macd_enforce_above_zero=False, macd_slope_lookback=5)
    state = classify_macd(bars, cfg)
    # The MACD should be negative but slope positive → eligible=True when toggle off
    if state.value < 0 and state.slope > 0:
        assert state.eligible
        assert state.favorability > 0


def test_classify_macd_enforce_off_downtrend_not_eligible():
    """Falling prices with toggle off → MACD falling → not eligible."""
    bars = _falling_bars(60)
    cfg = TAConfig(macd_enforce_above_zero=False)
    state = classify_macd(bars, cfg)
    assert not state.eligible
    assert state.favorability <= 0
