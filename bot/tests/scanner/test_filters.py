"""Unit tests for each scanner filter — individually, with no network."""

from __future__ import annotations

import pytest

from bot.scanner.filters import (
    compute_gap_pct,
    compute_rvol,
    passes_float_filter,
    passes_gap_up_filter,
    passes_news_filter,
    passes_price_filter,
    passes_rvol_filter,
)


# ---------------------------------------------------------------------------
# Price filter
# ---------------------------------------------------------------------------

class TestPriceFilter:
    def test_within_range(self) -> None:
        assert passes_price_filter(5.0, 1.0, 20.0) is True

    def test_at_min(self) -> None:
        assert passes_price_filter(1.0, 1.0, 20.0) is True

    def test_at_max(self) -> None:
        assert passes_price_filter(20.0, 1.0, 20.0) is True

    def test_below_min(self) -> None:
        assert passes_price_filter(0.99, 1.0, 20.0) is False

    def test_above_max(self) -> None:
        assert passes_price_filter(20.01, 1.0, 20.0) is False

    def test_zero_price(self) -> None:
        assert passes_price_filter(0.0, 1.0, 20.0) is False


# ---------------------------------------------------------------------------
# Gap-up filter
# ---------------------------------------------------------------------------

class TestGapUpFilter:
    def test_exactly_at_threshold(self) -> None:
        # 5% above prev_close
        assert passes_gap_up_filter(10.5, 10.0, 5.0) is True

    def test_above_threshold(self) -> None:
        assert passes_gap_up_filter(12.0, 10.0, 5.0) is True  # +20%

    def test_below_threshold(self) -> None:
        assert passes_gap_up_filter(10.4, 10.0, 5.0) is False  # +4%

    def test_gap_down(self) -> None:
        assert passes_gap_up_filter(9.0, 10.0, 5.0) is False  # -10%

    def test_zero_prev_close(self) -> None:
        assert passes_gap_up_filter(10.0, 0.0, 5.0) is False

    def test_compute_gap_pct(self) -> None:
        pct = compute_gap_pct(11.0, 10.0)
        assert abs(pct - 10.0) < 0.001

    def test_compute_gap_pct_negative(self) -> None:
        pct = compute_gap_pct(9.0, 10.0)
        assert pct < 0


# ---------------------------------------------------------------------------
# RVOL filter
# ---------------------------------------------------------------------------

class TestRvolFilter:
    def test_high_rvol_passes(self) -> None:
        # today: 1M shares in 30% of session; avg daily: 500k → RVOL = 1M/(500k*0.3) ≈ 6.67
        rvol = compute_rvol(1_000_000, 500_000, 0.3)
        assert rvol > 2.0
        assert passes_rvol_filter(rvol, 2.0) is True

    def test_low_rvol_fails(self) -> None:
        # today: 100k shares in 50% of session; avg daily: 500k → RVOL = 100k/250k = 0.4
        rvol = compute_rvol(100_000, 500_000, 0.5)
        assert passes_rvol_filter(rvol, 2.0) is False

    def test_exactly_at_threshold(self) -> None:
        # RVOL = 2.0 exactly
        rvol = compute_rvol(200_000, 200_000, 0.5)  # 200k / (200k * 0.5) = 2.0
        assert passes_rvol_filter(rvol, 2.0) is True

    def test_zero_avg_returns_zero(self) -> None:
        rvol = compute_rvol(100_000, 0, 0.5)
        assert rvol == 0.0

    def test_zero_elapsed_returns_zero(self) -> None:
        rvol = compute_rvol(100_000, 500_000, 0.0)
        assert rvol == 0.0

    def test_rvol_calculation_matches_formula(self) -> None:
        # RVOL = volume / (avg * elapsed)
        v, avg, f = 300_000, 200_000, 0.5
        expected = v / (avg * f)
        assert abs(compute_rvol(v, avg, f) - expected) < 1e-9


# ---------------------------------------------------------------------------
# Float filter
# ---------------------------------------------------------------------------

class TestFloatFilter:
    def test_small_float_passes(self) -> None:
        assert passes_float_filter(10_000_000, False, 20_000_000) is True

    def test_at_max_passes(self) -> None:
        assert passes_float_filter(20_000_000, False, 20_000_000) is True

    def test_too_large_fails(self) -> None:
        assert passes_float_filter(25_000_000, False, 20_000_000) is False

    def test_unknown_float_passes(self) -> None:
        # Unknown float always passes float filter (tradability handled separately)
        assert passes_float_filter(None, True, 20_000_000) is True

    def test_none_float_passes(self) -> None:
        assert passes_float_filter(None, False, 20_000_000) is True


# ---------------------------------------------------------------------------
# News filter
# ---------------------------------------------------------------------------

class TestNewsFilter:
    def test_has_news_and_required(self) -> None:
        assert passes_news_filter(True, True) is True

    def test_no_news_required_fails(self) -> None:
        assert passes_news_filter(False, True) is False

    def test_no_news_not_required_passes(self) -> None:
        assert passes_news_filter(False, False) is True

    def test_has_news_not_required_still_passes(self) -> None:
        assert passes_news_filter(True, False) is True
