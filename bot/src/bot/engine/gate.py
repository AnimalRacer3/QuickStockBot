from __future__ import annotations

from dataclasses import dataclass

from bot.models import Bar
from bot.ta.helpers import vwap
from bot.ta.models import MacdState

# Bearish reversal / topping pattern tags that disqualify an entry.
_BEARISH_TAGS = frozenset(
    [
        "bearish_engulfing",
        "shooting_star",
        "evening_star",
        "bearish_continuation",
        "dark_cloud_cover",
        "hanging_man",
    ]
)


@dataclass
class GateResult:
    passed: bool
    reason: str = ""


def _has_higher_highs(bars: list[Bar], lookback: int = 3) -> bool:
    """Return True if each of the last `lookback` candle highs is higher than the one before."""
    if len(bars) < lookback:
        return False
    window = [float(b.high) for b in bars[-lookback:]]
    return all(window[i] > window[i - 1] for i in range(1, len(window)))


def _price_above_vwap(bars: list[Bar]) -> bool:
    """Return True if the latest close is above the session VWAP."""
    if not bars:
        return False
    session_vwap = vwap(bars)
    return float(bars[-1].close) > session_vwap


def _is_overextended(bars: list[Bar], overextension_pct: float) -> bool:
    """Return True if price has rallied more than `overextension_pct` above VWAP."""
    if not bars:
        return True
    session_vwap = vwap(bars)
    price = float(bars[-1].close)
    if session_vwap <= 0:
        return False
    pct_above = (price - session_vwap) / session_vwap * 100.0
    return pct_above > overextension_pct


def _macd_eligible_rising(macd: MacdState) -> bool:
    """MACD must be eligible AND have a rising (positive) slope."""
    return macd.eligible and macd.slope > 0


def check_entry_gate(
    bars: list[Bar],
    macd: MacdState,
    pattern_tags: list[str],
    score_setup: float,
    enabled_patterns: list[str],
    conviction_threshold: float,
    overextension_pct: float,
    lookback: int = 3,
) -> GateResult:
    """
    Full entry gate check.

    Returns GateResult(passed=True) only when ALL conditions pass:
      1. Higher highs (front-side momentum)
      2. Price above VWAP
      3. MACD eligible with rising favorability
      4. At least one enabled bullish pattern present
      5. No bearish reversal / topping pattern
      6. Not overextended
      7. Conviction gate: score_setup >= conviction_threshold
    """
    if not _has_higher_highs(bars, lookback):
        return GateResult(passed=False, reason="no higher highs (back-side)")

    if not _price_above_vwap(bars):
        return GateResult(passed=False, reason="price below VWAP")

    if not _macd_eligible_rising(macd):
        return GateResult(passed=False, reason="MACD not eligible or not rising")

    active_bullish = [t for t in pattern_tags if t in enabled_patterns]
    if not active_bullish:
        return GateResult(passed=False, reason="no enabled bullish pattern")

    bearish_hits = [t for t in pattern_tags if t in _BEARISH_TAGS]
    if bearish_hits:
        return GateResult(
            passed=False,
            reason=f"bearish/topping pattern detected: {bearish_hits}",
        )

    if _is_overextended(bars, overextension_pct):
        return GateResult(passed=False, reason="price overextended above VWAP")

    if score_setup < conviction_threshold:
        return GateResult(
            passed=False,
            reason=f"conviction below threshold ({score_setup:.3f} < {conviction_threshold:.3f})",
        )

    return GateResult(passed=True, reason="all gates passed")
