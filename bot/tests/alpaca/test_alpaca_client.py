"""Unit tests for AlpacaClient — all HTTP calls mocked via respx (no network)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
import respx

from bot.alpaca.client import AlpacaClient
from bot.alpaca.config import AlpacaConfig
from bot.models import (
    AccountSnapshot,
    Asset,
    Bar,
    NewsItem,
    Order,
    OrderSide,
    OrderStatus,
    OrderType,
    Position,
    Quote,
)

CASSETTE_DIR = Path(__file__).parent / "cassettes"

_PAPER_CONFIG = AlpacaConfig(
    api_key="test-key",
    secret_key="test-secret",
    base_url="https://paper-api.alpaca.markets",
    data_url="https://data.alpaca.markets",
    is_paper=True,
)

_START = datetime(2024, 1, 15, 14, 30, 0, tzinfo=timezone.utc)
_END = datetime(2024, 1, 15, 15, 30, 0, tzinfo=timezone.utc)


def _cassette(name: str) -> dict | list:  # type: ignore[type-arg]
    return json.loads((CASSETTE_DIR / name).read_text())


def _make_client() -> AlpacaClient:
    http = httpx.Client(
        headers={
            "APCA-API-KEY-ID": _PAPER_CONFIG.api_key,
            "APCA-API-SECRET-KEY": _PAPER_CONFIG.secret_key,
        },
    )
    return AlpacaClient(config=_PAPER_CONFIG, http_client=http)


# ---------------------------------------------------------------------------
# Bars
# ---------------------------------------------------------------------------


class TestGetBars:
    @respx.mock
    def test_returns_bar_list(self) -> None:
        payload = _cassette("get_bars.json")
        respx.get("https://data.alpaca.markets/v2/stocks/AAPL/bars").mock(
            return_value=httpx.Response(200, json=payload)
        )
        bars = _make_client().get_bars("AAPL", _START, _END)
        assert len(bars) == 2
        assert all(isinstance(b, Bar) for b in bars)

    @respx.mock
    def test_bar_fields_mapped_correctly(self) -> None:
        payload = _cassette("get_bars.json")
        respx.get("https://data.alpaca.markets/v2/stocks/AAPL/bars").mock(
            return_value=httpx.Response(200, json=payload)
        )
        bar = _make_client().get_bars("AAPL", _START, _END)[0]
        assert bar.symbol == "AAPL"
        assert bar.open == Decimal("183.92")
        assert bar.high == Decimal("184.15")
        assert bar.low == Decimal("183.80")
        assert bar.close == Decimal("184.10")
        assert bar.volume == 125430
        assert bar.vwap == Decimal("184.02")
        assert bar.trade_count == 742
        assert bar.timeframe == "1Min"

    @respx.mock
    def test_empty_bars_returns_empty_list(self) -> None:
        respx.get("https://data.alpaca.markets/v2/stocks/AAPL/bars").mock(
            return_value=httpx.Response(200, json={"bars": [], "symbol": "AAPL"})
        )
        assert _make_client().get_bars("AAPL", _START, _END) == []


# ---------------------------------------------------------------------------
# Quote
# ---------------------------------------------------------------------------


class TestGetLatestQuote:
    @respx.mock
    def test_returns_quote(self) -> None:
        payload = _cassette("get_latest_quote.json")
        respx.get("https://data.alpaca.markets/v2/stocks/AAPL/quotes/latest").mock(
            return_value=httpx.Response(200, json=payload)
        )
        quote = _make_client().get_latest_quote("AAPL")
        assert isinstance(quote, Quote)
        assert quote.symbol == "AAPL"
        assert quote.bid_price == Decimal("184.18")
        assert quote.ask_price == Decimal("184.20")
        assert quote.bid_size == 1
        assert quote.ask_size == 2

    @respx.mock
    def test_mid_price_is_average(self) -> None:
        payload = _cassette("get_latest_quote.json")
        respx.get("https://data.alpaca.markets/v2/stocks/AAPL/quotes/latest").mock(
            return_value=httpx.Response(200, json=payload)
        )
        quote = _make_client().get_latest_quote("AAPL")
        assert quote.mid_price == (Decimal("184.18") + Decimal("184.20")) / Decimal("2")

    @respx.mock
    def test_get_latest_price_returns_mid(self) -> None:
        payload = _cassette("get_latest_quote.json")
        respx.get("https://data.alpaca.markets/v2/stocks/AAPL/quotes/latest").mock(
            return_value=httpx.Response(200, json=payload)
        )
        price = _make_client().get_latest_price("AAPL")
        assert price == Decimal("184.19")


# ---------------------------------------------------------------------------
# Assets
# ---------------------------------------------------------------------------


class TestListAssets:
    @respx.mock
    def test_returns_asset_list(self) -> None:
        payload = _cassette("list_assets.json")
        respx.get("https://paper-api.alpaca.markets/v2/assets").mock(
            return_value=httpx.Response(200, json=payload)
        )
        assets = _make_client().list_assets()
        assert len(assets) == 2
        assert all(isinstance(a, Asset) for a in assets)
        assert assets[0].symbol == "AAPL"
        assert assets[0].tradable is True
        assert assets[0].asset_class == "us_equity"
        assert assets[1].symbol == "TSLA"


# ---------------------------------------------------------------------------
# News
# ---------------------------------------------------------------------------


class TestGetNews:
    @respx.mock
    def test_returns_news_list(self) -> None:
        payload = _cassette("get_news.json")
        respx.get("https://data.alpaca.markets/v1beta1/news").mock(
            return_value=httpx.Response(200, json=payload)
        )
        news = _make_client().get_news(["AAPL"])
        assert len(news) == 1
        item = news[0]
        assert isinstance(item, NewsItem)
        assert item.id == 31547580
        assert "Apple" in item.headline
        assert "AAPL" in item.symbols
        assert item.source == "benzinga"


# ---------------------------------------------------------------------------
# Orders
# ---------------------------------------------------------------------------


class TestSubmitOrder:
    @respx.mock
    def test_market_buy_mapped(self) -> None:
        payload = _cassette("submit_order.json")
        respx.post("https://paper-api.alpaca.markets/v2/orders").mock(
            return_value=httpx.Response(200, json=payload)
        )
        order = _make_client().submit_order(
            symbol="AAPL",
            qty=Decimal("1"),
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
        )
        assert isinstance(order, Order)
        assert order.symbol == "AAPL"
        assert order.side == OrderSide.BUY
        assert order.order_type == OrderType.MARKET
        assert order.status == OrderStatus.ACCEPTED
        assert order.qty == Decimal("1")
        assert order.filled_qty == Decimal("0")
        assert order.limit_price is None

    @respx.mock
    def test_limit_order_includes_price(self) -> None:
        base = dict(_cassette("submit_order.json"))  # type: ignore[arg-type]
        base.update({"type": "limit", "limit_price": "180.00"})
        respx.post("https://paper-api.alpaca.markets/v2/orders").mock(
            return_value=httpx.Response(200, json=base)
        )
        order = _make_client().submit_order(
            symbol="AAPL",
            qty=Decimal("1"),
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            limit_price=Decimal("180.00"),
        )
        assert order.order_type == OrderType.LIMIT
        assert order.limit_price == Decimal("180.00")

    @respx.mock
    def test_short_sell_side(self) -> None:
        base = dict(_cassette("submit_order.json"))  # type: ignore[arg-type]
        base.update({"side": "sell", "qty": "5"})
        respx.post("https://paper-api.alpaca.markets/v2/orders").mock(
            return_value=httpx.Response(200, json=base)
        )
        order = _make_client().submit_order(
            symbol="AAPL",
            qty=Decimal("5"),
            side=OrderSide.SELL,
            order_type=OrderType.MARKET,
        )
        assert order.side == OrderSide.SELL
        assert order.qty == Decimal("5")


class TestGetOrder:
    @respx.mock
    def test_filled_order_status(self) -> None:
        order_id = "61e69015-8549-4bfd-b9c3-01e75843f47d"
        payload = _cassette("get_order_filled.json")
        respx.get(f"https://paper-api.alpaca.markets/v2/orders/{order_id}").mock(
            return_value=httpx.Response(200, json=payload)
        )
        order = _make_client().get_order(order_id)
        assert order.status == OrderStatus.FILLED
        assert order.filled_qty == Decimal("1")
        assert order.filled_avg_price == Decimal("184.05")
        assert order.filled_at is not None


class TestStatusMapping:
    @pytest.mark.parametrize(
        "raw_status,expected",
        [
            ("new", OrderStatus.NEW),
            ("partially_filled", OrderStatus.PARTIALLY_FILLED),
            ("filled", OrderStatus.FILLED),
            ("canceled", OrderStatus.CANCELED),
            ("expired", OrderStatus.EXPIRED),
            ("rejected", OrderStatus.REJECTED),
            ("accepted", OrderStatus.ACCEPTED),
            ("pending_new", OrderStatus.PENDING_NEW),
        ],
    )
    @respx.mock
    def test_all_status_values_map(
        self, raw_status: str, expected: OrderStatus
    ) -> None:
        order_id = "61e69015-8549-4bfd-b9c3-01e75843f47d"
        base = dict(_cassette("get_order_filled.json"))  # type: ignore[arg-type]
        base["status"] = raw_status
        respx.get(f"https://paper-api.alpaca.markets/v2/orders/{order_id}").mock(
            return_value=httpx.Response(200, json=base)
        )
        assert _make_client().get_order(order_id).status == expected


# ---------------------------------------------------------------------------
# Positions
# ---------------------------------------------------------------------------


class TestListPositions:
    @respx.mock
    def test_returns_position_list(self) -> None:
        payload = _cassette("list_positions.json")
        respx.get("https://paper-api.alpaca.markets/v2/positions").mock(
            return_value=httpx.Response(200, json=payload)
        )
        positions = _make_client().list_positions()
        assert len(positions) == 1
        pos = positions[0]
        assert isinstance(pos, Position)
        assert pos.symbol == "AAPL"
        assert pos.qty == Decimal("10")
        assert pos.avg_entry_price == Decimal("178.50")
        assert pos.side == "long"


# ---------------------------------------------------------------------------
# Account
# ---------------------------------------------------------------------------


class TestGetAccount:
    @respx.mock
    def test_account_fields_mapped(self) -> None:
        payload = _cassette("get_account.json")
        respx.get("https://paper-api.alpaca.markets/v2/account").mock(
            return_value=httpx.Response(200, json=payload)
        )
        account = _make_client().get_account()
        assert isinstance(account, AccountSnapshot)
        assert account.buying_power == Decimal("200000.00")
        assert account.equity == Decimal("101841.00")
        assert account.cash == Decimal("100000.00")
        assert account.day_trade_count == 0
        assert account.pattern_day_trader is False
        assert account.is_pdt_restricted is False

    @respx.mock
    def test_pdt_flag_triggers_restriction_below_25k(self) -> None:
        base = dict(_cassette("get_account.json"))  # type: ignore[arg-type]
        base.update(
            {
                "pattern_day_trader": True,
                "equity": "24999.00",
                "portfolio_value": "24999.00",
            }
        )
        respx.get("https://paper-api.alpaca.markets/v2/account").mock(
            return_value=httpx.Response(200, json=base)
        )
        account = _make_client().get_account()
        assert account.pattern_day_trader is True
        assert account.is_pdt_restricted is True

    @respx.mock
    def test_pdt_flag_not_restricted_above_25k(self) -> None:
        base = dict(_cassette("get_account.json"))  # type: ignore[arg-type]
        base.update(
            {
                "pattern_day_trader": True,
                "equity": "25001.00",
                "portfolio_value": "25001.00",
            }
        )
        respx.get("https://paper-api.alpaca.markets/v2/account").mock(
            return_value=httpx.Response(200, json=base)
        )
        account = _make_client().get_account()
        assert account.pattern_day_trader is True
        assert account.is_pdt_restricted is False


# ---------------------------------------------------------------------------
# Retry behaviour
# ---------------------------------------------------------------------------


class TestRetryBehavior:
    @respx.mock
    def test_retries_on_500_then_succeeds(self) -> None:
        payload = _cassette("get_bars.json")
        route = respx.get("https://data.alpaca.markets/v2/stocks/AAPL/bars")
        route.side_effect = [
            httpx.Response(500, json={"message": "internal error"}),
            httpx.Response(200, json=payload),
        ]
        bars = _make_client().get_bars("AAPL", _START, _END)
        assert len(bars) == 2

    @respx.mock
    def test_raises_after_max_retries(self) -> None:
        route = respx.get("https://data.alpaca.markets/v2/stocks/AAPL/bars")
        route.side_effect = [
            httpx.Response(503, json={"message": "unavailable"}),
            httpx.Response(503, json={"message": "unavailable"}),
            httpx.Response(503, json={"message": "unavailable"}),
            httpx.Response(503, json={"message": "unavailable"}),
        ]
        with pytest.raises(httpx.HTTPStatusError):
            _make_client().get_bars("AAPL", _START, _END)

    @respx.mock
    def test_non_transient_error_not_retried(self) -> None:
        route = respx.get("https://data.alpaca.markets/v2/stocks/AAPL/bars")
        route.side_effect = [
            httpx.Response(422, json={"message": "unprocessable"}),
        ]
        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            _make_client().get_bars("AAPL", _START, _END)
        assert exc_info.value.response.status_code == 422
