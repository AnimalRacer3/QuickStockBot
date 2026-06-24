from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from uuid import uuid4

from bot.alpaca.client import MarketClient
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
    TimeInForce,
)

_NOW = datetime(2024, 1, 15, 14, 30, 0, tzinfo=timezone.utc)


class FakeMarketClient(MarketClient):
    """Deterministic in-memory client for unit tests.

    Callers may adjust ``_order_terminal_status`` to simulate different
    terminal states; all other fixture data is hardcoded.
    """

    def __init__(self) -> None:
        self._submitted_orders: list[Order] = []
        self._order_terminal_status: OrderStatus = OrderStatus.FILLED

    # ------------------------------------------------------------------
    # MarketClient implementation
    # ------------------------------------------------------------------

    def get_bars(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        timeframe: str = "1Min",
        limit: int = 1000,
    ) -> list[Bar]:
        base = Decimal("100")
        return [
            Bar(
                symbol=symbol,
                timestamp=_NOW,
                open=base + i,
                high=base + i + Decimal("2"),
                low=base + i - Decimal("1"),
                close=base + i + Decimal("1"),
                volume=10_000 + i * 100,
                vwap=base + i + Decimal("0.5"),
                trade_count=500 + i,
                timeframe=timeframe,
            )
            for i in range(3)
        ]

    def get_latest_quote(self, symbol: str) -> Quote:
        return Quote(
            symbol=symbol,
            timestamp=_NOW,
            bid_price=Decimal("149.95"),
            bid_size=100,
            ask_price=Decimal("150.05"),
            ask_size=100,
        )

    def get_latest_price(self, symbol: str) -> Decimal:
        return self.get_latest_quote(symbol).mid_price

    def list_assets(self) -> list[Asset]:
        return [
            Asset(
                id="b0b6dd9d-8b9b-48a9-ba46-b9d54afdffd8",
                symbol="AAPL",
                name="Apple Inc.",
                exchange="NASDAQ",
                asset_class="us_equity",
                tradable=True,
                marginable=True,
                shortable=True,
                easy_to_borrow=True,
                fractionable=True,
            ),
            Asset(
                id="8ccae427-5dd0-45b3-b5fe-7ba5e422c766",
                symbol="TSLA",
                name="Tesla Inc.",
                exchange="NASDAQ",
                asset_class="us_equity",
                tradable=True,
                marginable=True,
                shortable=True,
                easy_to_borrow=True,
                fractionable=True,
            ),
        ]

    def get_news(self, symbols: list[str], limit: int = 10) -> list[NewsItem]:
        return [
            NewsItem(
                id=1001,
                headline="Apple Reports Record Quarterly Revenue",
                summary="Apple Inc. reported record revenue for Q1 2024.",
                author="Jane Smith",
                created_at=_NOW,
                updated_at=_NOW,
                url="https://example.com/news/1001",
                symbols=symbols[:1] if symbols else ["AAPL"],
                source="Benzinga",
            )
        ]

    def submit_order(
        self,
        symbol: str,
        qty: Decimal,
        side: OrderSide,
        order_type: OrderType,
        time_in_force: TimeInForce = TimeInForce.DAY,
        limit_price: Optional[Decimal] = None,
    ) -> Order:
        order = Order(
            id=str(uuid4()),
            client_order_id=str(uuid4()),
            symbol=symbol,
            side=side,
            order_type=order_type,
            qty=qty,
            filled_qty=Decimal("0"),
            limit_price=limit_price,
            status=OrderStatus.NEW,
            time_in_force=time_in_force,
            submitted_at=_NOW,
        )
        self._submitted_orders.append(order)
        return order

    def get_order(self, order_id: str) -> Order:
        for o in self._submitted_orders:
            if o.id == order_id:
                return o.model_copy(
                    update={
                        "status": self._order_terminal_status,
                        "filled_qty": o.qty,
                        "filled_at": _NOW,
                        "filled_avg_price": Decimal("150.00"),
                    }
                )
        raise KeyError(f"Order {order_id!r} not found in FakeMarketClient")

    def poll_order(
        self,
        order_id: str,
        timeout_seconds: float = 60.0,
        poll_interval: float = 1.0,
    ) -> Order:
        return self.get_order(order_id)

    def list_positions(self) -> list[Position]:
        return [
            Position(
                symbol="AAPL",
                qty=Decimal("10"),
                avg_entry_price=Decimal("145.00"),
                market_value=Decimal("1500.00"),
                unrealized_pl=Decimal("50.00"),
                unrealized_plpc=Decimal("0.034"),
                current_price=Decimal("150.00"),
                side="long",
            )
        ]

    def get_account(self) -> AccountSnapshot:
        return AccountSnapshot(
            buying_power=Decimal("100000.00"),
            equity=Decimal("110000.00"),
            cash=Decimal("50000.00"),
            portfolio_value=Decimal("110000.00"),
            pattern_day_trader=False,
            day_trade_count=0,
            day_trading_buying_power=Decimal("0"),
            is_pdt_restricted=False,
        )
