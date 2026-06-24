from __future__ import annotations

from bot.ta.models import MacdState, PatternMatch, TickerTA

_EPS = 1e-10


def compute_score(
    symbol: str,
    has_news: bool,
    sentiment_score: float,
    macd_state: MacdState,
    pattern_matches: list[PatternMatch],
    price: float,
    high: float,
    low: float,
) -> tuple[float, TickerTA]:
    """
    Combine signals into a numeric score in [0, 100] and a TickerTA.

    Budget (raw max ≈ 80, always clamped to [0, 100]):
      News presence            :  +5
      Sentiment (×10, ±10)    : -10 … +10
      MACD favorability (×30) :   0 … +30
      Pattern strength (×15)  :   0 … +20  (capped)
      Price-in-range (×10)    :   0 … +10
    """
    raw = 0.0

    # News & sentiment component
    if has_news:
        raw += 5.0
        raw += max(-10.0, min(10.0, sentiment_score * 10.0))

    # MACD component: only add positive contribution when eligible
    if macd_state.eligible:
        raw += macd_state.favorability * 30.0

    # Pattern component (capped at 20)
    pattern_total = sum(m.strength for m in pattern_matches if m.matched)
    raw += min(20.0, pattern_total * 15.0)

    # Price-in-range: lower in the day's range → more room to run → higher score
    day_range = high - low
    if day_range > _EPS:
        position = (price - low) / day_range  # 0 = at low, 1 = at high
        raw += (1.0 - position) * 10.0

    score = max(0.0, min(100.0, raw))

    pattern_tags = [m.tag for m in pattern_matches if m.matched]

    return score, TickerTA(
        symbol=symbol,
        macd_state=macd_state,
        pattern_tags=pattern_tags,
        score=score,
    )
