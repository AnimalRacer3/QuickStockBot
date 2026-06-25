"""Tests: feature logging matches engine output (incl. all new fields)."""

from __future__ import annotations

import math

import pytest

from bot.learning.features import (
    FEATURE_ORDER,
    KNOWN_PATTERN_TAGS,
    extract_features,
    features_to_vector,
)
from bot.scanner.models import TickerState
from bot.ta.models import MacdState


def _make_macd(
    value: float = 0.2,
    slope: float = 0.1,
    hist: float = 0.05,
    favorability: float = 0.5,
    eligible: bool = True,
) -> MacdState:
    return MacdState(
        value=value, slope=slope, hist=hist, favorability=favorability, eligible=eligible
    )


def _make_state(
    symbol: str = "AAPL",
    price: float = 10.0,
    prev_close: float = 9.0,
    gap_pct: float = 11.1,
    pct_change: float = 11.1,
    rvol: float = 3.5,
    float_shares: int | None = 5_000_000,
    unknown_float: bool = False,
    tradable: bool = True,
    has_news: bool = True,
    macd_state: MacdState | None = None,
    pattern_tags: list[str] | None = None,
    role: str = "leader",
    score: float = 72.0,
) -> TickerState:
    return TickerState(
        symbol=symbol,
        price=price,
        prev_close=prev_close,
        gap_pct=gap_pct,
        pct_change=pct_change,
        rvol=rvol,
        float_shares=float_shares,
        unknown_float=unknown_float,
        tradable=tradable,
        has_news=has_news,
        macd_state=macd_state or _make_macd(),
        pattern_tags=pattern_tags or [],
        pattern_signature=[0.1] * 25,
        role=role,
        score=score,
    )


# ---------------------------------------------------------------------------
# Key coverage
# ---------------------------------------------------------------------------


def test_extract_features_has_all_feature_order_keys():
    state = _make_state()
    features = extract_features(state, sentiment_score=0.5, time_of_day_frac=0.25, sizing=500.0)
    for key in FEATURE_ORDER:
        assert key in features, f"Missing feature: {key}"


def test_extract_features_news_sentiment_matches_input():
    state = _make_state()
    features = extract_features(state, sentiment_score=0.85, time_of_day_frac=0.0, sizing=0.0)
    assert features["news_sentiment"] == pytest.approx(0.85)
    assert features["has_news"] == 1.0


def test_extract_features_zero_sentiment_clears_has_news():
    state = _make_state()
    features = extract_features(state, sentiment_score=0.0, time_of_day_frac=0.0, sizing=0.0)
    assert features["news_sentiment"] == pytest.approx(0.0)
    assert features["has_news"] == 0.0


def test_extract_features_macd_fields_match_state():
    macd = _make_macd(value=1.23, slope=-0.5, hist=0.07, favorability=0.3, eligible=True)
    state = _make_state(macd_state=macd)
    features = extract_features(state, sentiment_score=0.0, time_of_day_frac=0.0, sizing=0.0)

    assert features["macd_value"] == pytest.approx(1.23)
    assert features["macd_slope"] == pytest.approx(-0.5)
    assert features["macd_hist"] == pytest.approx(0.07)
    assert features["macd_favorability"] == pytest.approx(0.3)
    assert features["macd_eligible"] == 1.0


def test_extract_features_macd_ineligible():
    macd = _make_macd(eligible=False)
    state = _make_state(macd_state=macd)
    features = extract_features(state, sentiment_score=0.0, time_of_day_frac=0.0, sizing=0.0)
    assert features["macd_eligible"] == 0.0


def test_extract_features_rvol():
    state = _make_state(rvol=4.2)
    features = extract_features(state, sentiment_score=0.0, time_of_day_frac=0.0, sizing=0.0)
    assert features["rvol"] == pytest.approx(4.2)


def test_extract_features_float_shares_log():
    state = _make_state(float_shares=5_000_000)
    features = extract_features(state, sentiment_score=0.0, time_of_day_frac=0.0, sizing=0.0)
    assert features["float_shares_log"] == pytest.approx(math.log1p(5_000_000))
    assert features["unknown_float"] == 0.0


def test_extract_features_unknown_float():
    state = _make_state(float_shares=None, unknown_float=True)
    features = extract_features(state, sentiment_score=0.0, time_of_day_frac=0.0, sizing=0.0)
    assert features["float_shares_log"] == 0.0
    assert features["unknown_float"] == 1.0


def test_extract_features_pct_change_and_gap():
    state = _make_state(pct_change=15.0, gap_pct=12.5)
    features = extract_features(state, sentiment_score=0.0, time_of_day_frac=0.0, sizing=0.0)
    assert features["pct_change"] == pytest.approx(15.0)
    assert features["gap_pct"] == pytest.approx(12.5)


def test_extract_features_role_leader():
    state = _make_state(role="leader")
    features = extract_features(state, sentiment_score=0.0, time_of_day_frac=0.0, sizing=0.0)
    assert features["role_leader"] == 1.0
    assert features["role_laggard"] == 0.0


def test_extract_features_role_laggard():
    state = _make_state(role="laggard")
    features = extract_features(state, sentiment_score=0.0, time_of_day_frac=0.0, sizing=0.0)
    assert features["role_leader"] == 0.0
    assert features["role_laggard"] == 1.0


def test_extract_features_role_standalone():
    state = _make_state(role="standalone")
    features = extract_features(state, sentiment_score=0.0, time_of_day_frac=0.0, sizing=0.0)
    assert features["role_leader"] == 0.0
    assert features["role_laggard"] == 0.0


def test_extract_features_time_of_day_and_sizing():
    state = _make_state()
    features = extract_features(state, sentiment_score=0.0, time_of_day_frac=0.33, sizing=1234.5)
    assert features["time_of_day_frac"] == pytest.approx(0.33)
    assert features["sizing"] == pytest.approx(1234.5)


def test_extract_features_all_patterns_active():
    state = _make_state(pattern_tags=list(KNOWN_PATTERN_TAGS))
    features = extract_features(state, sentiment_score=0.0, time_of_day_frac=0.0, sizing=0.0)
    for tag in KNOWN_PATTERN_TAGS:
        assert features[f"pattern_{tag}"] == 1.0, f"pattern_{tag} should be 1.0"


def test_extract_features_no_patterns():
    state = _make_state(pattern_tags=[])
    features = extract_features(state, sentiment_score=0.0, time_of_day_frac=0.0, sizing=0.0)
    for tag in KNOWN_PATTERN_TAGS:
        assert features[f"pattern_{tag}"] == 0.0


def test_extract_features_partial_patterns():
    active = ["hammer"]
    state = _make_state(pattern_tags=active)
    features = extract_features(state, sentiment_score=0.0, time_of_day_frac=0.0, sizing=0.0)
    assert features["pattern_hammer"] == 1.0
    assert features["pattern_bullish_engulfing"] == 0.0
    assert features["pattern_morning_star"] == 0.0
    assert features["pattern_bullish_continuation"] == 0.0


def test_extract_features_score_matches_state():
    state = _make_state(score=88.5)
    features = extract_features(state, sentiment_score=0.0, time_of_day_frac=0.0, sizing=0.0)
    assert features["score"] == pytest.approx(88.5)


def test_features_to_vector_length():
    state = _make_state()
    features = extract_features(state, sentiment_score=0.5, time_of_day_frac=0.2, sizing=300.0)
    vec = features_to_vector(features)
    assert len(vec) == len(FEATURE_ORDER)


def test_features_to_vector_order_matches_feature_order():
    state = _make_state(rvol=7.7, score=55.0, role="laggard")
    features = extract_features(state, sentiment_score=-0.3, time_of_day_frac=0.9, sizing=999.0)
    vec = features_to_vector(features)
    for i, key in enumerate(FEATURE_ORDER):
        assert vec[i] == pytest.approx(features[key]), f"Mismatch at index {i} ({key})"


def test_features_to_vector_missing_keys_default_zero():
    # Simulate a partial feature dict (older schema)
    partial: dict[str, float] = {"rvol": 3.0, "score": 50.0}
    vec = features_to_vector(partial)
    rvol_idx = list(FEATURE_ORDER).index("rvol")
    score_idx = list(FEATURE_ORDER).index("score")
    assert vec[rvol_idx] == pytest.approx(3.0)
    assert vec[score_idx] == pytest.approx(50.0)
    # All other positions should be 0.0
    for i, key in enumerate(FEATURE_ORDER):
        if key not in ("rvol", "score"):
            assert vec[i] == pytest.approx(0.0), f"Expected 0 at {key}"
