"""Pattern signature and similarity tests — no network required."""
from __future__ import annotations

import math

import pytest

from bot.ta.similarity import pattern_signature, pattern_similarity
from tests.ta.conftest import make_bar


def _simple_bars(n: int = 5) -> list:
    return [make_bar(10.0, 11.0, 9.5, 10.5, volume=100_000) for _ in range(n)]


# ---------------------------------------------------------------------------
# pattern_signature
# ---------------------------------------------------------------------------


def test_signature_length():
    bars = _simple_bars(5)
    sig = pattern_signature(bars)
    assert len(sig) == 5 * 5  # 5 features per candle


def test_signature_empty():
    assert pattern_signature([]) == []


def test_signature_volume_normalized():
    """Volume field: single bar → vol/mean_vol = 1.0."""
    bar = make_bar(10.0, 11.0, 9.5, 10.5, volume=50_000)
    sig = pattern_signature([bar])
    # 5th feature (index 4) is normalised volume; single bar → 1.0
    assert abs(sig[4] - 1.0) < 1e-6


def test_signature_body_ratio_doji():
    """A doji (open == close) has body_ratio ≈ 0."""
    bar = make_bar(10.0, 11.0, 9.0, 10.0, volume=100_000)
    sig = pattern_signature([bar])
    body_ratio = sig[1]  # second feature
    assert abs(body_ratio) < 1e-6


# ---------------------------------------------------------------------------
# pattern_similarity
# ---------------------------------------------------------------------------


def test_similarity_identical():
    bars = _simple_bars(5)
    sig = pattern_signature(bars)
    s = pattern_similarity(sig, sig)
    assert abs(s - 1.0) < 1e-9


def test_similarity_symmetry():
    bars_a = _simple_bars(5)
    bars_b = [make_bar(20.0, 22.0, 19.0, 21.0) for _ in range(5)]
    sig_a = pattern_signature(bars_a)
    sig_b = pattern_signature(bars_b)
    assert abs(pattern_similarity(sig_a, sig_b) - pattern_similarity(sig_b, sig_a)) < 1e-9


def test_similarity_in_range():
    bars_a = _simple_bars(5)
    bars_b = [make_bar(20.0, 22.0, 19.0, 21.0) for _ in range(5)]
    sig_a = pattern_signature(bars_a)
    sig_b = pattern_signature(bars_b)
    s = pattern_similarity(sig_a, sig_b)
    assert 0.0 <= s <= 1.0


def test_similarity_dissimilar_low():
    """
    Strong-body bullish (full candle, no wicks) vs. hammer-bearish (tiny body
    at top, long lower wick) should have clearly different signatures.
    """
    # Full bullish body: ret≈0.22, body_r=1.0, upper_r=0, lower_r=0, vol_n=1
    full_bullish = [make_bar(9.0, 11.0, 9.0, 11.0) for _ in range(5)]
    # Hammer-bearish: tiny body, long lower wick → body_r≈0.05, lower_r≈0.91
    hammer_bear = [make_bar(10.1, 10.2, 8.0, 10.0) for _ in range(5)]
    sig_fb = pattern_signature(full_bullish)
    sig_hb = pattern_signature(hammer_bear)
    s = pattern_similarity(sig_fb, sig_hb)
    assert s < 0.8


def test_similarity_empty_vectors():
    assert pattern_similarity([], []) == 0.0


def test_similarity_mismatched_length():
    assert pattern_similarity([1.0, 2.0], [1.0]) == 0.0
