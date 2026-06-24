"""Float (shares outstanding) lookup via Finnhub, cached once per day."""

from __future__ import annotations

import logging
import os
from datetime import date
from typing import Optional

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

# In-process daily cache: {(symbol, date) -> shares}
_CACHE: dict[tuple[str, date], Optional[int]] = {}


def _is_transient(exc: BaseException) -> bool:
    if isinstance(exc, httpx.TimeoutException):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in {429, 500, 502, 503, 504}
    return False


@retry(
    retry=retry_if_exception(_is_transient),
    wait=wait_exponential(multiplier=1, min=1, max=16),
    stop=stop_after_attempt(3),
    reraise=True,
)
def _fetch_finnhub(symbol: str, api_key: str) -> Optional[int]:
    """Fetch shareOutstanding from Finnhub /stock/profile2.

    Returns shares as an integer (Finnhub reports millions → multiply by 1e6),
    or None if unavailable.
    """
    url = "https://finnhub.io/api/v1/stock/profile2"
    resp = httpx.get(url, params={"symbol": symbol, "token": api_key}, timeout=10.0)
    resp.raise_for_status()
    data = resp.json()
    outstanding = data.get("shareOutstanding")
    if outstanding is None or outstanding == 0:
        return None
    # Finnhub reports in millions
    return int(float(outstanding) * 1_000_000)


def get_float_shares(
    symbol: str,
    api_key: Optional[str] = None,
    today: Optional[date] = None,
    http_client: Optional[httpx.Client] = None,
) -> Optional[int]:
    """Return shares outstanding for *symbol*, cached once per calendar day.

    Returns None when the Finnhub key is absent, the symbol is unknown,
    or the request fails.  Callers should set unknown_float=True on None.
    """
    key = api_key or os.environ.get("FINNHUB_API_KEY")
    if not key:
        logger.debug("FINNHUB_API_KEY not set — float unavailable for %s", symbol)
        return None

    cache_date = today or date.today()
    cache_key = (symbol, cache_date)
    if cache_key in _CACHE:
        return _CACHE[cache_key]

    try:
        if http_client is not None:
            # Testable override: call through provided client
            resp = http_client.get(
                "https://finnhub.io/api/v1/stock/profile2",
                params={"symbol": symbol, "token": key},
            )
            resp.raise_for_status()
            data = resp.json()
            outstanding = data.get("shareOutstanding")
            shares: Optional[int] = (
                int(float(outstanding) * 1_000_000) if outstanding else None
            )
        else:
            shares = _fetch_finnhub(symbol, key)
    except Exception as exc:
        logger.warning("Float lookup failed for %s: %s", symbol, exc)
        shares = None

    _CACHE[cache_key] = shares
    return shares


def clear_cache() -> None:
    """Clear the in-process float cache (useful in tests)."""
    _CACHE.clear()
