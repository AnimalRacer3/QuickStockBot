"""Feature extraction from scanner TickerState for ML training and inference."""

from __future__ import annotations

import math

from bot.scanner.models import TickerState

# All pattern tags the scanner can produce (must stay in sync with ta/patterns.py).
KNOWN_PATTERN_TAGS: tuple[str, ...] = (
    "bullish_engulfing",
    "hammer",
    "morning_star",
    "bullish_continuation",
)

# Canonical feature order used when converting a feature dict to a numpy array.
# Extend this list (append only) when adding new features to avoid breaking
# existing serialised models.
FEATURE_ORDER: tuple[str, ...] = (
    # News / sentiment
    "news_sentiment",
    "has_news",
    # MACD
    "macd_value",
    "macd_slope",
    "macd_hist",
    "macd_favorability",
    "macd_eligible",
    # Volume / float
    "rvol",
    "float_shares_log",
    "unknown_float",
    # Price momentum
    "pct_change",
    "gap_pct",
    # Role encoding
    "role_leader",
    "role_laggard",
    # Timing and sizing context
    "time_of_day_frac",
    "sizing",
    # Aggregate score from TA engine
    "score",
    # Pattern binary flags (one per KNOWN_PATTERN_TAGS)
    *[f"pattern_{tag}" for tag in KNOWN_PATTERN_TAGS],
)


def extract_features(
    state: TickerState,
    *,
    sentiment_score: float,
    time_of_day_frac: float,
    sizing: float,
) -> dict[str, float]:
    """Build a feature dict from a TickerState plus context at entry time.

    Args:
        state: Scanner output for the ticker at the moment of entry evaluation.
        sentiment_score: Aggregate news sentiment score in [-1, 1].
        time_of_day_frac: Fraction of the regular session elapsed (0 = open, 1 = close).
        sizing: Position size used for the trade (e.g. USD notional or share count).

    Returns:
        A flat dict with keys matching FEATURE_ORDER.
    """
    pattern_set = set(state.pattern_tags)

    float_log = (
        math.log1p(float(state.float_shares)) if state.float_shares is not None else 0.0
    )

    features: dict[str, float] = {
        "news_sentiment": float(sentiment_score),
        "has_news": 1.0 if sentiment_score != 0.0 else 0.0,
        "macd_value": float(state.macd_state.value),
        "macd_slope": float(state.macd_state.slope),
        "macd_hist": float(state.macd_state.hist),
        "macd_favorability": float(state.macd_state.favorability),
        "macd_eligible": 1.0 if state.macd_state.eligible else 0.0,
        "rvol": float(state.rvol),
        "float_shares_log": float_log,
        "unknown_float": 1.0 if state.unknown_float else 0.0,
        "pct_change": float(state.pct_change),
        "gap_pct": float(state.gap_pct),
        "role_leader": 1.0 if state.role == "leader" else 0.0,
        "role_laggard": 1.0 if state.role == "laggard" else 0.0,
        "time_of_day_frac": float(time_of_day_frac),
        "sizing": float(sizing),
        "score": float(state.score),
    }

    for tag in KNOWN_PATTERN_TAGS:
        features[f"pattern_{tag}"] = 1.0 if tag in pattern_set else 0.0

    return features


def features_to_vector(features: dict[str, float]) -> list[float]:
    """Convert a feature dict to an ordered list matching FEATURE_ORDER.

    Missing keys default to 0.0 so that samples from older code paths can still
    be scored by a model trained on a superset of features.
    """
    return [features.get(key, 0.0) for key in FEATURE_ORDER]
