from __future__ import annotations

import math

from bot.models import Bar

_EPS = 1e-10


def pattern_signature(bars: list[Bar]) -> list[float]:
    """
    Build a feature vector for a candle window.

    Per candle (in order):
      - Normalised return:    (close - open) / open
      - Body ratio:           |close - open| / (high - low)
      - Upper-wick ratio:     (high - max(open, close)) / (high - low)
      - Lower-wick ratio:     (min(open, close) - low) / (high - low)
      - Normalised volume:    volume / mean_volume

    Returns a flat list of length 5 × len(bars).
    """
    if not bars:
        return []

    mean_vol = sum(b.volume for b in bars) / len(bars)

    vector: list[float] = []
    for b in bars:
        o, h, l, c = float(b.open), float(b.high), float(b.low), float(b.close)
        rng = h - l

        ret = (c - o) / (o + _EPS)
        body_r = abs(c - o) / (rng + _EPS)
        upper_r = (h - max(o, c)) / (rng + _EPS)
        lower_r = (min(o, c) - l) / (rng + _EPS)
        vol_n = b.volume / (mean_vol + _EPS)

        vector.extend([ret, body_r, upper_r, lower_r, vol_n])

    return vector


def pattern_similarity(a: list[float], b: list[float]) -> float:
    """
    Cosine similarity between two pattern signature vectors.
    Returns a value in [0, 1]; identical vectors → 1.0, orthogonal → 0.0.
    """
    if not a or not b or len(a) != len(b):
        return 0.0

    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))

    if norm_a < _EPS or norm_b < _EPS:
        return 0.0

    # Clamp to [0, 1]: cosine can be negative for dissimilar patterns.
    return max(0.0, min(1.0, dot / (norm_a * norm_b)))
