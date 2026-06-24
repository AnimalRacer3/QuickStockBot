"""Pattern detector tests — no network required."""
from __future__ import annotations

import pytest

from bot.ta.config import TAConfig
from bot.ta.patterns import (
    detect_bullish_continuation,
    detect_bullish_engulfing,
    detect_hammer,
    detect_morning_star,
    run_enabled_patterns,
)
from tests.ta.conftest import make_bar


# ---------------------------------------------------------------------------
# bullish_engulfing
# ---------------------------------------------------------------------------


def test_bullish_engulfing_match():
    prev = make_bar(open_=10.0, high=10.5, low=9.0, close=9.2)  # bearish
    curr = make_bar(open_=8.8, high=11.0, low=8.5, close=10.5)  # bullish, engulfs
    result = detect_bullish_engulfing([prev, curr])
    assert result.matched
    assert result.tag == "bullish_engulfing"
    assert 0.0 < result.strength <= 1.0


def test_bullish_engulfing_no_match_both_bullish():
    prev = make_bar(9.0, 10.5, 8.8, 10.0)
    curr = make_bar(9.5, 11.0, 9.2, 10.8)
    result = detect_bullish_engulfing([prev, curr])
    assert not result.matched


def test_bullish_engulfing_no_match_partial_engulf():
    prev = make_bar(10.0, 10.5, 9.5, 9.6)  # bearish
    curr = make_bar(9.7, 10.2, 9.4, 9.9)   # bullish but doesn't engulf (open too high)
    result = detect_bullish_engulfing([prev, curr])
    assert not result.matched


def test_bullish_engulfing_too_few_bars():
    result = detect_bullish_engulfing([make_bar(10.0, 11.0, 9.0, 10.5)])
    assert not result.matched


# ---------------------------------------------------------------------------
# hammer
# ---------------------------------------------------------------------------


def test_hammer_match():
    # Small body at top, long lower wick, tiny upper wick
    # open=10, close=10.1, high=10.15, low=8.0
    # body=0.1, lower_wick=10-8=2, upper_wick=10.15-10.1=0.05
    candle = make_bar(open_=10.0, high=10.15, low=8.0, close=10.1)
    result = detect_hammer([candle])
    assert result.matched
    assert result.tag == "hammer"
    assert result.strength > 0.5


def test_hammer_no_match_large_upper_wick():
    # upper wick > body disqualifies
    candle = make_bar(open_=10.0, high=11.5, low=8.0, close=10.1)
    result = detect_hammer([candle])
    assert not result.matched


def test_hammer_no_match_insufficient_lower_wick():
    # body=0.5, lower_wick=0.3 (< 2×0.5=1.0) → should not match
    # open=10.0, close=10.5, high=10.6, low=9.7
    # upper_wick=0.1 < body=0.5 ✓, lower_wick=0.3 < 2*body=1.0 → no match
    candle = make_bar(open_=10.0, high=10.6, low=9.7, close=10.5)
    result = detect_hammer([candle])
    assert not result.matched


def test_hammer_no_bars():
    result = detect_hammer([])
    assert not result.matched


# ---------------------------------------------------------------------------
# morning_star
# ---------------------------------------------------------------------------


def test_morning_star_match():
    c1 = make_bar(open_=12.0, high=12.2, low=9.5, close=9.7)   # large bearish
    c2 = make_bar(open_=9.5,  high=9.8,  low=9.2, close=9.6)   # tiny body
    c3 = make_bar(open_=9.7,  high=12.5, low=9.5, close=11.5)  # bullish, above midpoint
    result = detect_morning_star([c1, c2, c3])
    assert result.matched
    assert result.tag == "morning_star"
    assert result.strength > 0.0


def test_morning_star_c3_not_above_midpoint():
    c1 = make_bar(12.0, 12.2, 9.5, 9.7)    # bearish, mid ≈ 10.85
    c2 = make_bar(9.5,  9.8,  9.2, 9.6)
    c3 = make_bar(9.7,  10.5, 9.5, 10.5)   # closes at 10.5, below mid 10.85
    result = detect_morning_star([c1, c2, c3])
    assert not result.matched


def test_morning_star_c2_too_large():
    c1 = make_bar(12.0, 12.2, 9.5, 9.7)
    c2 = make_bar(10.0, 11.0, 9.0, 11.0)   # big body
    c3 = make_bar(11.0, 13.0, 10.5, 12.5)
    result = detect_morning_star([c1, c2, c3])
    assert not result.matched


def test_morning_star_too_few_bars():
    result = detect_morning_star([make_bar(10.0, 11.0, 9.0, 9.5)])
    assert not result.matched


# ---------------------------------------------------------------------------
# bullish_continuation
# ---------------------------------------------------------------------------


def test_bullish_continuation_match():
    bars = [
        make_bar(10.0, 11.0, 9.8, 10.8),   # bullish
        make_bar(10.8, 11.5, 10.5, 11.3),  # bullish
        make_bar(11.3, 12.0, 11.0, 11.8),  # bullish
        make_bar(11.8, 12.5, 11.5, 12.3),  # bullish
        make_bar(12.3, 13.0, 12.0, 12.8),  # bullish
    ]
    result = detect_bullish_continuation(bars)
    assert result.matched
    assert result.strength == 1.0


def test_bullish_continuation_mixed_but_majority():
    bars = [
        make_bar(10.0, 11.0, 9.8, 10.8),  # bullish
        make_bar(10.8, 11.0, 10.0, 10.2), # bearish
        make_bar(10.2, 11.5, 10.0, 11.3), # bullish
        make_bar(11.3, 12.0, 11.0, 11.8), # bullish
    ]
    result = detect_bullish_continuation(bars)
    assert result.matched
    assert result.strength == pytest.approx(0.75)


def test_bullish_continuation_no_match_mostly_bearish():
    bars = [
        make_bar(12.0, 12.5, 11.0, 11.2),  # bearish
        make_bar(11.5, 12.0, 10.5, 10.8),  # bearish
        make_bar(11.0, 11.5, 10.0, 11.0),  # bullish (at close, same open→close actually bullish)
    ]
    result = detect_bullish_continuation(bars)
    assert not result.matched


def test_bullish_continuation_too_few_bars():
    result = detect_bullish_continuation([make_bar(10.0, 11.0, 9.5, 10.5)])
    assert not result.matched


# ---------------------------------------------------------------------------
# run_enabled_patterns
# ---------------------------------------------------------------------------


def test_run_enabled_patterns_filters_to_enabled():
    bars = [make_bar(10.0, 11.0, 9.5, 10.5)] * 5
    results = run_enabled_patterns(bars, enabled=["hammer"], lookback=5)
    assert len(results) == 1
    assert results[0].tag == "hammer"


def test_run_enabled_patterns_skips_unknown():
    bars = [make_bar(10.0, 11.0, 9.5, 10.5)] * 5
    results = run_enabled_patterns(bars, enabled=["nonexistent"], lookback=5)
    assert results == []


def test_run_enabled_patterns_respects_lookback():
    """Only the last `lookback` bars are passed to detectors."""
    # 10 bars, but lookback=2 means only the last 2 are used for engulfing detection
    bars = [
        make_bar(10.0, 10.5, 9.0, 9.2),  # bearish
        make_bar(8.8,  11.0, 8.5, 10.5), # bullish, engulfs
    ]
    results = run_enabled_patterns(bars, enabled=["bullish_engulfing"], lookback=2)
    assert results[0].matched
