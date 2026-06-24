"""Tests for FakeMarketClient — verifies all interface methods work deterministically."""
from __future__ import annotations

from decimal import Decimal

import pytest

from bot.alpaca.fake_client import FakeMarketClient
from shared.models import (
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
    TimeInForce,
)


@pytest.fixture()
def client() -> FakeMarketClient:
    return FakeMarketClient()


class TestFakeBars:
    def test_returns_bars(self, client: FakeMarketClient) -> None:
        from datetime import datetime, timezone
        start = datetime(2024, 1, 15, 14, 30, tzinfo=timezone.utc)
        end = datetime(2024, 1, 15, 15, 30, tzinfo=timezone.utc)
        bars = client.get_bars("AAPL", start, end)
        assert len(bars) == 3
        assert all(isinstance(b, Bar) for b in bars)
        assert all(b.symbol == "AAPL" for b in bars)

    def test_bars_are_deterministic(self, client: FakeMarketClient) -> None:
        from datetime import datetime, timezone
        start = datetime(2024, 1, 15, 14, 30, tzinfo=timezone.utc)
        end = datetime(2024, 1, 15, 15, 30, tzinfo=timezone.utc)
        bars1 = client.get_bars("AAPL", start, end)
        bars2 = client.get_bars("AAPL", start, end)
        assert [b.close for b in bars1] == [b.close for b in bars2]


class TestFakeQuote:
    def test_returns_quote(self, client: FakeMarketClient) -> None:
        q = client.get_latest_quote("AAPL")
        assert isinstance(q, Quote)
        assert q.symbol == "AAPL"
        assert q.bid_price < q.ask_price

    def test_price_is_mid(self, client: FakeMarketClient) -> None:
        q = client.get_latest_quote("TSLA")
        price = client.get_latest_price("TSLA")
        assert price == q.mid_price


class TestFakeAssets:
    def test_returns_asset_list(self, client: FakeMarketClient) -> None:
        assets = client.list_assets()
        assert len(assets) >= 1
        assert all(isinstance(a, Asset) for a in assets)
        symbols = [a.symbol for a in assets]
        assert "AAPL" in symbols

    def test_assets_are_tradable(self, client: FakeMarketClient) -> None:
        for asset in client.list_assets():
            assert asset.tradable is True


class TestFakeNews:
    def test_returns_news_item(self, client: FakeMarketClient) -> None:
        news = client.get_news(["AAPL"])
        assert len(news) >= 1
        assert all(isinstance(n, NewsItem) for n in news)

    def test_symbol_in_news(self, client: FakeMarketClient) -> None:
        news = client.get_news(["TSLA"])
        # FakeClient uses provided symbols
        assert any("TSLA" in n.symbols for n in news)


class TestFakeOrders:
    def test_submit_market_buy(self, client: FakeMarketClient) -> None:
        order = client.submit_order("AAPL", Decimal("1"), OrderSide.BUY, OrderType.MARKET)
        assert isinstance(order, Order)
        assert order.status == OrderStatus.NEW
        assert order.symbol == "AAPL"
        assert order.side == OrderSide.BUY
        assert order.order_type == OrderType.MARKET
        assert order.qty == Decimal("1")

    def test_submit_limit_sell(self, client: FakeMarketClient) -> None:
        order = client.submit_order(
            "TSLA",
            Decimal("5"),
            OrderSide.SELL,
            OrderType.LIMIT,
            limit_price=Decimal("250.00"),
        )
        assert order.limit_price == Decimal("250.00")
        assert order.side == OrderSide.SELL

    def test_get_order_returns_filled(self, client: FakeMarketClient) -> None:
        order = client.submit_order("AAPL", Decimal("1"), OrderSide.BUY, OrderType.MARKET)
        fetched = client.get_order(order.id)
        assert fetched.status == OrderStatus.FILLED
        assert fetched.filled_qty == Decimal("1")
        assert fetched.filled_avg_price is not None

    def test_get_unknown_order_raises(self, client: FakeMarketClient) -> None:
        with pytest.raises(KeyError):
            client.get_order("nonexistent-id")

    def test_poll_order_returns_immediately(self, client: FakeMarketClient) -> None:
        order = client.submit_order("AAPL", Decimal("2"), OrderSide.BUY, OrderType.MARKET)
        result = client.poll_order(order.id, timeout_seconds=0.001)
        assert result.status == OrderStatus.FILLED

    def test_each_order_gets_unique_id(self, client: FakeMarketClient) -> None:
        o1 = client.submit_order("AAPL", Decimal("1"), OrderSide.BUY, OrderType.MARKET)
        o2 = client.submit_order("AAPL", Decimal("1"), OrderSide.BUY, OrderType.MARKET)
        assert o1.id != o2.id


class TestFakePositions:
    def test_returns_positions(self, client: FakeMarketClient) -> None:
        positions = client.list_positions()
        assert len(positions) >= 1
        assert all(isinstance(p, Position) for p in positions)
        assert positions[0].symbol == "AAPL"
        assert positions[0].side == "long"


class TestFakeAccount:
    def test_returns_account(self, client: FakeMarketClient) -> None:
        acc = client.get_account()
        assert isinstance(acc, AccountSnapshot)
        assert acc.buying_power > Decimal("0")
        assert acc.equity > Decimal("0")
        assert acc.is_pdt_restricted is False
        assert acc.pattern_day_trader is False
        assert acc.day_trade_count == 0
