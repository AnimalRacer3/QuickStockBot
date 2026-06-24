"""Scoring tests — no network required."""

from __future__ import annotations

from bot.ta.models import MacdState, PatternMatch
from bot.ta.scoring import compute_score


def _macd(
    value: float = 1.0,
    slope: float = 0.1,
    hist: float = 0.05,
    favorability: float = 0.7,
    eligible: bool = True,
) -> MacdState:
    return MacdState(
        value=value,
        slope=slope,
        hist=hist,
        favorability=favorability,
        eligible=eligible,
    )


def _match(tag: str = "hammer", strength: float = 0.8) -> PatternMatch:
    return PatternMatch(matched=True, tag=tag, strength=strength)


def _no_match(tag: str = "morning_star") -> PatternMatch:
    return PatternMatch(matched=False, tag=tag, strength=0.0)


# ---------------------------------------------------------------------------
# Basic behaviour
# ---------------------------------------------------------------------------


def test_score_in_range() -> None:
    score, ta = compute_score(
        symbol="AAPL",
        has_news=True,
        sentiment_score=0.5,
        macd_state=_macd(),
        pattern_matches=[_match()],
        price=10.5,
        high=11.0,
        low=9.0,
    )
    assert 0.0 <= score <= 100.0
    assert ta.score == score


def test_score_determinism() -> None:
    """Same inputs always produce the same score."""
    s1, _ = compute_score(
        symbol="AAPL",
        has_news=True,
        sentiment_score=0.3,
        macd_state=_macd(favorability=0.6),
        pattern_matches=[_match("bullish_engulfing", 0.9)],
        price=10.0,
        high=12.0,
        low=9.0,
    )
    s2, _ = compute_score(
        symbol="AAPL",
        has_news=True,
        sentiment_score=0.3,
        macd_state=_macd(favorability=0.6),
        pattern_matches=[_match("bullish_engulfing", 0.9)],
        price=10.0,
        high=12.0,
        low=9.0,
    )
    assert s1 == s2


def test_score_no_news_lower_than_with_positive_news() -> None:
    macd = _macd()
    s_no, _ = compute_score(
        symbol="X",
        has_news=False,
        sentiment_score=0.8,
        macd_state=macd,
        pattern_matches=[],
        price=10.0,
        high=11.0,
        low=9.0,
    )
    s_yes, _ = compute_score(
        symbol="X",
        has_news=True,
        sentiment_score=0.8,
        macd_state=macd,
        pattern_matches=[],
        price=10.0,
        high=11.0,
        low=9.0,
    )
    assert s_yes > s_no


def test_score_ineligible_macd_lower() -> None:
    s_eligible, _ = compute_score(
        symbol="X",
        has_news=False,
        sentiment_score=0.0,
        macd_state=_macd(eligible=True, favorability=0.8),
        pattern_matches=[],
        price=10.0,
        high=11.0,
        low=9.0,
    )
    s_inelig, _ = compute_score(
        symbol="X",
        has_news=False,
        sentiment_score=0.0,
        macd_state=_macd(eligible=False, favorability=0.8),
        pattern_matches=[],
        price=10.0,
        high=11.0,
        low=9.0,
    )
    assert s_eligible > s_inelig


def test_score_patterns_increase_score() -> None:
    s_none, _ = compute_score(
        symbol="X",
        has_news=False,
        sentiment_score=0.0,
        macd_state=_macd(eligible=False, favorability=-1.0),
        pattern_matches=[],
        price=10.0,
        high=11.0,
        low=9.0,
    )
    s_match, _ = compute_score(
        symbol="X",
        has_news=False,
        sentiment_score=0.0,
        macd_state=_macd(eligible=False, favorability=-1.0),
        pattern_matches=[_match(strength=1.0)],
        price=10.0,
        high=11.0,
        low=9.0,
    )
    assert s_match > s_none


def test_pattern_tags_in_ticker_ta() -> None:
    _, ta = compute_score(
        symbol="TSLA",
        has_news=False,
        sentiment_score=0.0,
        macd_state=_macd(),
        pattern_matches=[_match("hammer"), _no_match("morning_star")],
        price=10.0,
        high=11.0,
        low=9.0,
    )
    assert "hammer" in ta.pattern_tags
    assert "morning_star" not in ta.pattern_tags


def test_macd_state_in_ticker_ta() -> None:
    state = _macd(favorability=0.9)
    _, ta = compute_score(
        symbol="TSLA",
        has_news=False,
        sentiment_score=0.0,
        macd_state=state,
        pattern_matches=[],
        price=10.0,
        high=11.0,
        low=9.0,
    )
    assert ta.macd_state is state


def test_price_at_low_scores_higher() -> None:
    """Price near day low → more room to run → higher score."""
    macd = _macd(eligible=False, favorability=-1.0)
    s_low, _ = compute_score(
        symbol="X",
        has_news=False,
        sentiment_score=0.0,
        macd_state=macd,
        pattern_matches=[],
        price=9.0,
        high=11.0,
        low=9.0,
    )
    s_high, _ = compute_score(
        symbol="X",
        has_news=False,
        sentiment_score=0.0,
        macd_state=macd,
        pattern_matches=[],
        price=11.0,
        high=11.0,
        low=9.0,
    )
    assert s_low > s_high


def test_negative_sentiment_reduces_score() -> None:
    macd = _macd(eligible=False, favorability=-1.0)
    s_pos, _ = compute_score(
        symbol="X",
        has_news=True,
        sentiment_score=1.0,
        macd_state=macd,
        pattern_matches=[],
        price=10.0,
        high=11.0,
        low=9.0,
    )
    s_neg, _ = compute_score(
        symbol="X",
        has_news=True,
        sentiment_score=-1.0,
        macd_state=macd,
        pattern_matches=[],
        price=10.0,
        high=11.0,
        low=9.0,
    )
    assert s_pos > s_neg


def test_score_clamped_minimum() -> None:
    """Score cannot go below 0 even with maximally bad inputs."""
    score, _ = compute_score(
        symbol="X",
        has_news=True,
        sentiment_score=-1.0,
        macd_state=_macd(eligible=False, favorability=-1.0),
        pattern_matches=[],
        price=11.0,
        high=11.0,
        low=9.0,
    )
    assert score >= 0.0


def test_score_clamped_maximum() -> None:
    """Score cannot exceed 100."""
    score, _ = compute_score(
        symbol="X",
        has_news=True,
        sentiment_score=1.0,
        macd_state=_macd(eligible=True, favorability=1.0),
        pattern_matches=[_match(strength=1.0)] * 10,
        price=9.0,
        high=11.0,
        low=9.0,
    )
    assert score <= 100.0
