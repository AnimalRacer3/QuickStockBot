"""Entry gate tests — Section 6."""

from __future__ import annotations

from bot.engine.gate import (
    _has_higher_highs,
    _is_overextended,
    _macd_eligible_rising,
    _price_above_vwap,
    check_entry_gate,
)
from bot.ta.models import MacdState
from tests.engine.conftest import make_bar, make_falling_bars, make_rising_bars

_ENABLED = ["bullish_engulfing", "hammer", "morning_star", "bullish_continuation"]


def _macd(eligible: bool = True, slope: float = 0.1, value: float = 1.0) -> MacdState:
    return MacdState(
        value=value, slope=slope, hist=0.05, favorability=0.7, eligible=eligible
    )


class TestHigherHighs:
    def test_rising_bars_pass(self) -> None:
        bars = make_rising_bars(n=5)
        assert _has_higher_highs(bars, lookback=3)

    def test_falling_bars_fail(self) -> None:
        bars = make_falling_bars(n=5)
        assert not _has_higher_highs(bars, lookback=3)

    def test_too_few_bars(self) -> None:
        bars = make_rising_bars(n=1)
        assert not _has_higher_highs(bars, lookback=3)

    def test_flat_bars_fail(self) -> None:
        bars = [make_bar(100, 101, 99, 100) for _ in range(5)]
        assert not _has_higher_highs(bars, lookback=3)


class TestPriceAboveVwap:
    def test_rising_bars_above_vwap(self) -> None:
        bars = make_rising_bars(n=20)
        assert _price_above_vwap(bars)

    def test_falling_bars_below_vwap(self) -> None:
        bars = make_falling_bars(n=20)
        assert not _price_above_vwap(bars)


class TestMacdEligibleRising:
    def test_eligible_and_rising(self) -> None:
        assert _macd_eligible_rising(_macd(eligible=True, slope=0.1))

    def test_eligible_but_flat_slope_fails(self) -> None:
        assert not _macd_eligible_rising(_macd(eligible=True, slope=0.0))

    def test_eligible_but_negative_slope_fails(self) -> None:
        assert not _macd_eligible_rising(_macd(eligible=True, slope=-0.1))

    def test_not_eligible_fails(self) -> None:
        assert not _macd_eligible_rising(_macd(eligible=False, slope=0.5))


class TestOverextended:
    def test_not_overextended(self) -> None:
        # Bars where close stays very close to VWAP
        bars = [make_bar(100, 100.5, 99.5, 100.1) for _ in range(20)]
        assert not _is_overextended(bars, overextension_pct=3.0)

    def test_very_high_price_overextended(self) -> None:
        # price at 200, vwap near 100 → 100% above → overextended
        bars = [make_bar(100, 101, 99, 200)] * 20
        assert _is_overextended(bars, overextension_pct=3.0)


class TestFullGate:
    def _rising_bars(self) -> list:
        return make_rising_bars(n=40)

    def test_front_side_accept(self) -> None:
        # Use a generous overextension_pct since rising bars naturally move above early VWAP
        bars = self._rising_bars()
        macd = _macd(eligible=True, slope=0.1)
        result = check_entry_gate(
            bars=bars,
            macd=macd,
            pattern_tags=["bullish_continuation"],
            score_setup=0.8,
            enabled_patterns=_ENABLED,
            conviction_threshold=0.6,
            overextension_pct=15.0,
        )
        assert result.passed

    def test_back_side_reject_no_higher_highs(self) -> None:
        bars = make_falling_bars(n=10)
        macd = _macd(eligible=True, slope=0.1)
        result = check_entry_gate(
            bars=bars,
            macd=macd,
            pattern_tags=["bullish_engulfing"],
            score_setup=0.9,
            enabled_patterns=_ENABLED,
            conviction_threshold=0.6,
            overextension_pct=3.0,
        )
        assert not result.passed
        assert "higher highs" in result.reason or "back-side" in result.reason

    def test_conviction_below_threshold_skip(self) -> None:
        bars = self._rising_bars()
        macd = _macd(eligible=True, slope=0.1)
        result = check_entry_gate(
            bars=bars,
            macd=macd,
            pattern_tags=["bullish_continuation"],
            score_setup=0.3,  # below threshold
            enabled_patterns=_ENABLED,
            conviction_threshold=0.6,
            overextension_pct=15.0,
        )
        assert not result.passed
        assert "conviction" in result.reason

    def test_conviction_at_threshold_accepted(self) -> None:
        bars = self._rising_bars()
        macd = _macd(eligible=True, slope=0.1)
        result = check_entry_gate(
            bars=bars,
            macd=macd,
            pattern_tags=["bullish_continuation"],
            score_setup=0.6,  # exactly at threshold
            enabled_patterns=_ENABLED,
            conviction_threshold=0.6,
            overextension_pct=15.0,
        )
        assert result.passed

    def test_bearish_pattern_blocks_entry(self) -> None:
        bars = self._rising_bars()
        macd = _macd(eligible=True, slope=0.1)
        result = check_entry_gate(
            bars=bars,
            macd=macd,
            pattern_tags=["bullish_continuation", "bearish_engulfing"],
            score_setup=0.9,
            enabled_patterns=_ENABLED,
            conviction_threshold=0.6,
            overextension_pct=15.0,
        )
        assert not result.passed
        assert "bearish" in result.reason or "topping" in result.reason

    def test_no_bullish_pattern_blocks_entry(self) -> None:
        bars = self._rising_bars()
        macd = _macd(eligible=True, slope=0.1)
        result = check_entry_gate(
            bars=bars,
            macd=macd,
            pattern_tags=[],  # no patterns
            score_setup=0.9,
            enabled_patterns=_ENABLED,
            conviction_threshold=0.6,
            overextension_pct=15.0,
        )
        assert not result.passed
        assert "bullish pattern" in result.reason

    def test_macd_not_eligible_blocks(self) -> None:
        bars = self._rising_bars()
        macd = _macd(eligible=False, slope=0.1)
        result = check_entry_gate(
            bars=bars,
            macd=macd,
            pattern_tags=["bullish_continuation"],
            score_setup=0.9,
            enabled_patterns=_ENABLED,
            conviction_threshold=0.6,
            overextension_pct=15.0,
        )
        assert not result.passed
        assert "MACD" in result.reason

    def test_macd_not_rising_blocks(self) -> None:
        bars = self._rising_bars()
        macd = _macd(eligible=True, slope=-0.05)
        result = check_entry_gate(
            bars=bars,
            macd=macd,
            pattern_tags=["bullish_continuation"],
            score_setup=0.9,
            enabled_patterns=_ENABLED,
            conviction_threshold=0.6,
            overextension_pct=15.0,
        )
        assert not result.passed
