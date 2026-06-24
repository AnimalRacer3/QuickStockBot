"""Individual candidate filters — each a pure predicate, independently testable."""

from __future__ import annotations

_EPS = 1e-10


def passes_price_filter(price: float, min_price: float, max_price: float) -> bool:
    """True when *price* is within [min_price, max_price]."""
    return min_price <= price <= max_price


def passes_gap_up_filter(price: float, prev_close: float, min_pct: float) -> bool:
    """True when today's price is at least *min_pct*% above *prev_close*.

    gap_pct = (price - prev_close) / prev_close × 100
    """
    if prev_close < _EPS:
        return False
    gap_pct = (price - prev_close) / prev_close * 100.0
    return gap_pct >= min_pct


def compute_gap_pct(price: float, prev_close: float) -> float:
    """Return gap-up percentage; negative = gap-down."""
    if prev_close < _EPS:
        return 0.0
    return (price - prev_close) / prev_close * 100.0


def compute_rvol(
    today_volume: int,
    avg_daily_volume: float,
    session_elapsed_fraction: float,
) -> float:
    """Compute relative volume (intraday approximation).

    RVOL = today_volume / (avg_daily_volume × session_elapsed_fraction)

    *session_elapsed_fraction* is the fraction of the regular trading session
    that has elapsed (0 < f ≤ 1).  We use 6.5 h as the session length.

    Approximation note: avg_daily_volume is a trailing ~20-session average of
    full-day volumes; dividing by the elapsed fraction converts it to the
    expected volume for this point in the session, so RVOL > 1 means trading
    faster than normal for this time of day.  Early-session values are volatile
    because the denominator is small.
    """
    if avg_daily_volume < _EPS or session_elapsed_fraction < _EPS:
        return 0.0
    expected = avg_daily_volume * session_elapsed_fraction
    return today_volume / expected


def passes_rvol_filter(rvol: float, min_rvol: float) -> bool:
    """True when RVOL meets the minimum threshold."""
    return rvol >= min_rvol


def passes_float_filter(
    float_shares: int | None,
    unknown_float: bool,
    max_float: int,
) -> bool:
    """True when the float is ≤ max_float, or unknown (unknown passes here;
    tradability is handled separately via include_unknown_float)."""
    if unknown_float or float_shares is None:
        return True  # unknown float: don't filter out; flag it
    return float_shares <= max_float


def passes_news_filter(has_news: bool, require_news: bool) -> bool:
    """True when the ticker has a recent positive article, or news is not required."""
    if not require_news:
        return True
    return has_news
