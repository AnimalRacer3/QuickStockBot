"""Candlestick pattern engine.

Every detector is a pure function over the last N *completed* 1-minute
candles (3 to 6 candles -- no 1- or 2-candle patterns). Each takes optional
VWAP/high-of-day context where the formation's definition requires it, and
returns a `PatternMatch` (naming the exact candles that formed it) or
`None`. Detectors have no I/O and no config dependency, which keeps them
trivially unit-testable against fixture data.
"""

from __future__ import annotations

from dataclasses import dataclass

from trader.models import Candle


@dataclass(frozen=True)
class PatternMatch:
    pattern: str
    candles: tuple[Candle, ...]
    entry_price: float

    @property
    def candle_timestamps(self) -> list[str]:
        return [c.timestamp.isoformat() for c in self.candles]


def _body_ratio(c: Candle) -> float:
    return c.body / c.range if c.range > 0 else 0.0


def _upper_wick_ratio(c: Candle) -> float:
    return c.upper_wick / c.range if c.range > 0 else 0.0


def _opens_within_prior_body(prior: Candle, curr: Candle) -> bool:
    lo, hi = sorted((prior.open, prior.close))
    return lo <= curr.open <= hi


# --------------------------------------------------------------------------
# Morning Star (3 candles)
# --------------------------------------------------------------------------


def detect_morning_star(candles: list[Candle]) -> PatternMatch | None:
    """Red body -> small-bodied indecision candle holding the low -> green
    candle closing above the first candle's midpoint, on rising volume."""
    if len(candles) < 3:
        return None
    c0, c1, c2 = candles[-3:]

    if not c0.is_red or _body_ratio(c0) < 0.4:
        return None
    if c1.body > c0.body * 0.5:
        return None
    if c1.high > c0.close * 1.002:  # c1 gaps/holds at or below the first candle's close
        return None
    if not c2.is_green:
        return None
    if c2.close <= c0.midpoint:
        return None
    if c2.volume <= c1.volume:  # rising volume into the reversal
        return None

    return PatternMatch("morning_star", (c0, c1, c2), entry_price=c2.close)


# --------------------------------------------------------------------------
# Three White Soldiers (3 candles)
# --------------------------------------------------------------------------


def detect_three_white_soldiers(candles: list[Candle]) -> PatternMatch | None:
    """Three consecutive green candles, each opening within the prior body
    and closing near its high, with no long upper wicks and steady volume."""
    if len(candles) < 3:
        return None
    c0, c1, c2 = candles[-3:]
    trio = (c0, c1, c2)

    if not all(c.is_green for c in trio):
        return None
    if not _opens_within_prior_body(c0, c1) or not _opens_within_prior_body(c1, c2):
        return None
    if any(_upper_wick_ratio(c) > 0.25 for c in trio):
        return None
    if c1.close <= c0.close or c2.close <= c1.close:  # each makes real progress
        return None
    volumes = [c.volume for c in trio]
    if min(volumes) <= 0 or max(volumes) / min(volumes) > 2.0:  # steady, not erratic
        return None

    return PatternMatch("three_white_soldiers", trio, entry_price=c2.close)


# --------------------------------------------------------------------------
# Rising Three Methods (5 candles)
# --------------------------------------------------------------------------


def detect_rising_three_methods(candles: list[Candle]) -> PatternMatch | None:
    """Strong green candle -> 3 small pullback candles holding above its low
    -> green candle closing above the first candle's high."""
    if len(candles) < 5:
        return None
    c0, c1, c2, c3, c4 = candles[-5:]

    if not c0.is_green or _body_ratio(c0) < 0.6:
        return None

    pullbacks = (c1, c2, c3)
    for p in pullbacks:
        if p.body > c0.body * 0.6:
            return None
        if p.low < c0.low:  # holds above the first candle's low
            return None
        if p.high > c0.high * 1.01:  # stays within the first candle's range
            return None

    if not c4.is_green or c4.close <= c0.high:
        return None

    return PatternMatch("rising_three_methods", (c0, c1, c2, c3, c4), entry_price=c4.close)


# --------------------------------------------------------------------------
# Pullback / bull flag (4-6 candles)
# --------------------------------------------------------------------------


def detect_pullback(candles: list[Candle], vwap_values: list[float]) -> PatternMatch | None:
    """Surge leg (1-2 strong green candles on heavy volume) -> 2-4 orderly
    pullback candles with declining volume, holding above VWAP and above a
    50% retrace of the surge -> entry the instant price breaks the high of
    the previous candle (the breakout candle == the last candle given).

    `vwap_values` must be the running VWAP aligned 1:1 with `candles`.
    Invalidated (returns None) if the pullback loses VWAP, retraces past
    50%, or runs longer than 4 candles without making a new high.
    """
    if len(vwap_values) != len(candles):
        raise ValueError("vwap_values must be aligned 1:1 with candles")

    for total_len in (6, 5, 4):
        if len(candles) < total_len:
            continue
        window = candles[-total_len:]
        vwap_window = vwap_values[-total_len:]

        for surge_len in (1, 2):
            pullback_len = total_len - surge_len - 1  # -1 for the breakout candle
            if pullback_len < 2 or pullback_len > 4:
                continue

            surge = window[:surge_len]
            pullback = window[surge_len:surge_len + pullback_len]
            breakout = window[-1]
            breakout_vwap = vwap_window[-1]

            match = _check_pullback_window(surge, pullback, breakout, breakout_vwap)
            if match is not None:
                return match
    return None


def _check_pullback_window(
    surge: list[Candle], pullback: list[Candle], breakout: Candle, breakout_vwap: float
) -> PatternMatch | None:
    if not all(c.is_green and _body_ratio(c) >= 0.5 for c in surge):
        return None

    surge_start = surge[0].low
    surge_high = max(c.high for c in surge)
    retrace_50_level = surge_high - 0.5 * (surge_high - surge_start)

    prev_volume = surge[-1].volume
    for p in pullback:
        if p.volume > prev_volume:  # declining volume through the pullback
            return None
        prev_volume = p.volume
        if p.low < retrace_50_level:  # exceeds 50% retrace
            return None
        # holding above VWAP: allow the low to wick slightly under, but the close must hold
        if p.close < retrace_50_level:
            return None

    if breakout.close < breakout_vwap:  # must hold VWAP through the breakout
        return None
    if breakout.high <= pullback[-1].high:  # must actually make a new high
        return None

    all_candles = tuple(surge) + tuple(pullback) + (breakout,)
    return PatternMatch("pullback", all_candles, entry_price=breakout.high)


# --------------------------------------------------------------------------
# Breakout base (3-6 candles)
# --------------------------------------------------------------------------


def detect_breakout_base(
    candles: list[Candle], high_of_day: float | None = None
) -> PatternMatch | None:
    """3-6 candles total: a tight (< ~2%) consolidation base near the high
    of day on declining volume, closed out by a candle that breaks the base
    high on >= 2x the base's average volume."""
    for total_len in (6, 5, 4, 3):
        if len(candles) < total_len:
            continue
        window = candles[-total_len:]
        base = window[:-1]
        breakout = window[-1]

        base_high = max(c.high for c in base)
        base_low = min(c.low for c in base)
        if base_low <= 0:
            continue
        base_range_pct = (base_high - base_low) / base_low * 100.0
        if base_range_pct >= 2.0:
            continue

        if high_of_day is not None and base_high < high_of_day * 0.98:
            continue

        base_volumes = [c.volume for c in base]
        half = len(base_volumes) // 2 or 1
        first_half_avg = sum(base_volumes[:half]) / half
        second_half_avg = sum(base_volumes[half:]) / (len(base_volumes) - half) if len(base_volumes) > half else first_half_avg
        if second_half_avg > first_half_avg:  # declining volume through the base
            continue

        base_avg_volume = sum(base_volumes) / len(base_volumes)
        if breakout.close <= base_high:
            continue
        if base_avg_volume <= 0 or breakout.volume < 2.0 * base_avg_volume:
            continue

        return PatternMatch("breakout_base", tuple(window), entry_price=breakout.close)

    return None


# --------------------------------------------------------------------------
# Registry
# --------------------------------------------------------------------------

PATTERN_NAMES = (
    "morning_star",
    "three_white_soldiers",
    "rising_three_methods",
    "pullback",
    "breakout_base",
)


def detect_all(
    candles: list[Candle],
    enabled: dict[str, bool],
    vwap_values: list[float] | None = None,
    high_of_day: float | None = None,
) -> list[PatternMatch]:
    """Run every enabled detector against the tail of `candles`, returning all matches."""
    matches: list[PatternMatch] = []

    if enabled.get("morning_star", True):
        m = detect_morning_star(candles)
        if m:
            matches.append(m)
    if enabled.get("three_white_soldiers", True):
        m = detect_three_white_soldiers(candles)
        if m:
            matches.append(m)
    if enabled.get("rising_three_methods", True):
        m = detect_rising_three_methods(candles)
        if m:
            matches.append(m)
    if enabled.get("pullback", True) and vwap_values is not None:
        m = detect_pullback(candles, vwap_values)
        if m:
            matches.append(m)
    if enabled.get("breakout_base", True):
        m = detect_breakout_base(candles, high_of_day)
        if m:
            matches.append(m)

    return matches
