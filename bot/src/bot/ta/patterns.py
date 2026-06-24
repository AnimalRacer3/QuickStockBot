from __future__ import annotations

from enum import Enum

from bot.models import Bar
from bot.ta.models import PatternMatch

_EPS = 1e-10


class PatternName(str, Enum):
    bullish_engulfing = "bullish_engulfing"
    hammer = "hammer"
    morning_star = "morning_star"
    bullish_continuation = "bullish_continuation"


def _body(bar: Bar) -> float:
    return abs(float(bar.close) - float(bar.open))


def _range(bar: Bar) -> float:
    return float(bar.high) - float(bar.low)


def _is_bullish(bar: Bar) -> bool:
    return float(bar.close) > float(bar.open)


def _is_bearish(bar: Bar) -> bool:
    return float(bar.open) > float(bar.close)


def detect_bullish_engulfing(bars: list[Bar]) -> PatternMatch:
    """
    Last candle is bullish and its body completely engulfs the prior bearish body.
    Requires at least 2 candles.
    """
    tag = PatternName.bullish_engulfing.value
    if len(bars) < 2:
        return PatternMatch(matched=False, tag=tag, strength=0.0)

    prev, curr = bars[-2], bars[-1]
    if not _is_bearish(prev) or not _is_bullish(curr):
        return PatternMatch(matched=False, tag=tag, strength=0.0)

    prev_open = float(prev.open)
    prev_close = float(prev.close)
    curr_open = float(curr.open)
    curr_close = float(curr.close)

    # Engulfing: current body wraps previous body
    if curr_open > prev_close or curr_close < prev_open:
        return PatternMatch(matched=False, tag=tag, strength=0.0)

    prev_body = _body(prev)
    curr_body = _body(curr)
    strength = min(1.0, curr_body / (prev_body + _EPS))
    return PatternMatch(matched=True, tag=tag, strength=round(strength, 4))


def detect_hammer(bars: list[Bar]) -> PatternMatch:
    """
    Small real body near the top of the range, lower wick ≥ 2× body,
    upper wick ≤ body.  Requires at least 1 candle.
    """
    tag = PatternName.hammer.value
    if not bars:
        return PatternMatch(matched=False, tag=tag, strength=0.0)

    candle = bars[-1]
    total = _range(candle)
    body = _body(candle)

    if total < _EPS:
        return PatternMatch(matched=False, tag=tag, strength=0.0)

    body_top = max(float(candle.open), float(candle.close))
    body_bot = min(float(candle.open), float(candle.close))
    upper_wick = float(candle.high) - body_top
    lower_wick = body_bot - float(candle.low)

    if lower_wick < 2.0 * body or upper_wick > body:
        return PatternMatch(matched=False, tag=tag, strength=0.0)

    # Strength: proportion of the total range occupied by the lower wick
    strength = min(1.0, lower_wick / total)
    return PatternMatch(matched=True, tag=tag, strength=round(strength, 4))


def detect_morning_star(bars: list[Bar]) -> PatternMatch:
    """
    Classic three-candle morning-star reversal:
      1. Large bearish candle.
      2. Small-body candle (indecision).
      3. Bullish candle closing above the midpoint of candle 1.
    Requires at least 3 candles.
    """
    tag = PatternName.morning_star.value
    if len(bars) < 3:
        return PatternMatch(matched=False, tag=tag, strength=0.0)

    c1, c2, c3 = bars[-3], bars[-2], bars[-1]

    # Candle 1: large bearish
    if not _is_bearish(c1):
        return PatternMatch(matched=False, tag=tag, strength=0.0)
    c1_body = _body(c1)
    if c1_body < _EPS:
        return PatternMatch(matched=False, tag=tag, strength=0.0)

    # Candle 2: small body (< 30 % of candle 1's body)
    if _body(c2) > 0.3 * c1_body:
        return PatternMatch(matched=False, tag=tag, strength=0.0)

    # Candle 3: bullish, closes above midpoint of candle 1
    if not _is_bullish(c3):
        return PatternMatch(matched=False, tag=tag, strength=0.0)
    c1_mid = (float(c1.open) + float(c1.close)) / 2.0
    if float(c3.close) <= c1_mid:
        return PatternMatch(matched=False, tag=tag, strength=0.0)

    # Strength: how far c3 closes into c1's body (0 = at midpoint, 1 = at/above c1 open)
    penetration = (float(c3.close) - c1_mid) / (float(c1.open) - c1_mid + _EPS)
    strength = min(1.0, max(0.0, penetration))
    return PatternMatch(matched=True, tag=tag, strength=round(strength, 4))


def detect_bullish_continuation(bars: list[Bar]) -> PatternMatch:
    """
    Majority of candles are bullish and the close is higher than the open of the
    first candle in the window (uptrend confirmed).  Requires at least 3 candles.
    """
    tag = PatternName.bullish_continuation.value
    if len(bars) < 3:
        return PatternMatch(matched=False, tag=tag, strength=0.0)

    bullish_count = sum(1 for b in bars if _is_bullish(b))
    majority = bullish_count > len(bars) / 2

    first_open = float(bars[0].open)
    last_close = float(bars[-1].close)
    uptrend = last_close > first_open

    if not majority or not uptrend:
        return PatternMatch(matched=False, tag=tag, strength=0.0)

    # Strength: fraction of candles that are bullish
    strength = bullish_count / len(bars)
    return PatternMatch(matched=True, tag=tag, strength=round(strength, 4))


_DETECTORS = {
    PatternName.bullish_engulfing.value: detect_bullish_engulfing,
    PatternName.hammer.value: detect_hammer,
    PatternName.morning_star.value: detect_morning_star,
    PatternName.bullish_continuation.value: detect_bullish_continuation,
}


def run_enabled_patterns(
    bars: list[Bar],
    enabled: list[str],
    lookback: int,
) -> list[PatternMatch]:
    """Run only the enabled pattern detectors on the last `lookback` candles."""
    window = bars[-lookback:] if len(bars) >= lookback else bars
    results: list[PatternMatch] = []
    for name in enabled:
        detector = _DETECTORS.get(name)
        if detector is not None:
            results.append(detector(window))
    return results
