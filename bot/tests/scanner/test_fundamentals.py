"""Tests for Finnhub float lookup with daily caching."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

import httpx
import pytest
import respx

from bot.scanner.fundamentals import clear_cache, get_float_shares


@pytest.fixture(autouse=True)
def _clear() -> None:
    clear_cache()


class TestGetFloatShares:
    @respx.mock
    def test_returns_shares_from_finnhub(self) -> None:
        respx.get("https://finnhub.io/api/v1/stock/profile2").mock(
            return_value=httpx.Response(200, json={"shareOutstanding": 10.0})
        )
        result = get_float_shares("TEST", api_key="fake-key", today=date(2024, 1, 2))
        assert result == 10_000_000

    @respx.mock
    def test_caches_result_for_same_day(self) -> None:
        respx.get("https://finnhub.io/api/v1/stock/profile2").mock(
            return_value=httpx.Response(200, json={"shareOutstanding": 5.0})
        )
        r1 = get_float_shares("AAPL", api_key="fake-key", today=date(2024, 1, 2))
        r2 = get_float_shares("AAPL", api_key="fake-key", today=date(2024, 1, 2))
        assert r1 == r2
        # Only one HTTP call despite two lookups
        assert respx.calls.call_count == 1

    @respx.mock
    def test_different_day_fetches_again(self) -> None:
        respx.get("https://finnhub.io/api/v1/stock/profile2").mock(
            return_value=httpx.Response(200, json={"shareOutstanding": 5.0})
        )
        get_float_shares("AAPL", api_key="fake-key", today=date(2024, 1, 2))
        get_float_shares("AAPL", api_key="fake-key", today=date(2024, 1, 3))
        assert respx.calls.call_count == 2

    @respx.mock
    def test_zero_outstanding_returns_none(self) -> None:
        respx.get("https://finnhub.io/api/v1/stock/profile2").mock(
            return_value=httpx.Response(200, json={"shareOutstanding": 0})
        )
        result = get_float_shares("UNKN", api_key="fake-key", today=date(2024, 1, 2))
        assert result is None

    @respx.mock
    def test_missing_key_returns_none(self) -> None:
        result = get_float_shares("TEST", api_key=None, today=date(2024, 1, 2))
        assert result is None
        assert respx.calls.call_count == 0

    @respx.mock
    def test_api_error_returns_none(self) -> None:
        respx.get("https://finnhub.io/api/v1/stock/profile2").mock(
            return_value=httpx.Response(500, json={})
        )
        result = get_float_shares("ERR", api_key="fake-key", today=date(2024, 1, 2))
        assert result is None

    def test_http_client_override(self) -> None:
        """When an http_client is provided, it is used instead of the real one."""
        mock_client = MagicMock(spec=httpx.Client)
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"shareOutstanding": 15.0}
        mock_resp.raise_for_status = MagicMock()
        mock_client.get.return_value = mock_resp

        result = get_float_shares(
            "FAKE", api_key="key", today=date(2024, 1, 2), http_client=mock_client
        )
        assert result == 15_000_000
        mock_client.get.assert_called_once()
