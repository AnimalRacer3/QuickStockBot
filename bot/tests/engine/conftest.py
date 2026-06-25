from __future__ import annotations

from datetime import datetime, timedelta, timezone
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

# Fixed session open / close for deterministic tests
_SESSION_OPEN = datetime(2024, 6, 10, 13, 30, 0, tzinfo=timezone.utc)  # 9:30 ET as UTC
_SESSION_CLOSE = datetime(2024, 6, 10, 20, 0, 0, tzinfo=timezone.utc)  # 16:00 ET as UTC
_FILL_PRICE = Decimal("100.00")


class FakeClock:
    """Injectable clock for deterministic session tests."""

    def __init__(
        self,
        now: datetime | None = None,
        session_open: datetime | None = None,
        market_open: bool = True,
        near_close: bool = False,
    ) -> None:
        self._now = now or datetime(2024, 6, 10, 14, 30, 0, tzinfo=timezone.utc)
        self._session_open = session_open or _SESSION_OPEN
        self._market_open = market_open
        self._near_close = near_close

    def now(self) -> datetime:
        return self._now

    def session_open(self) -> datetime:
        return self._session_open

    def is_market_open(self) -> bool:
        return self._market_open

    def is_near_close(self) -> bool:
        return self._near_close

    def advance(self, **kwargs: int) -> None:
        self._now = self._now + timedelta(**kwargs)


class ConfigurableMarketClient(MarketClient):
    """Configurable fake client for engine tests."""

    def __init__(
        self,
        equity: float = 100_000.0,
        buying_power: float = 100_000.0,
        day_trading_buying_power: float = 400_000.0,
        is_pdt: bool = False,
        is_pdt_restricted: bool = False,
        fill_price: float = 100.0,
        fill_status: OrderStatus = OrderStatus.FILLED,
        positions: list[Position] | None = None,
    ) -> None:
        self.equity = equity
        self.buying_power = buying_power
        self.day_trading_buying_power = day_trading_buying_power
        self.is_pdt = is_pdt
        self.is_pdt_restricted = is_pdt_restricted
        self.fill_price = fill_price
        self.fill_status = fill_status
        self._positions = positions or []
        self.submitted_orders: list[Order] = []

    def get_account(self) -> AccountSnapshot:
        return AccountSnapshot(
            buying_power=Decimal(str(self.buying_power)),
            equity=Decimal(str(self.equity)),
            cash=Decimal(str(self.buying_power)),
            portfolio_value=Decimal(str(self.equity)),
            pattern_day_trader=self.is_pdt,
            day_trade_count=0,
            day_trading_buying_power=Decimal(str(self.day_trading_buying_power)),
            is_pdt_restricted=self.is_pdt_restricted,
        )

    def get_bars(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        timeframe: str = "1Min",
        limit: int = 1000,
    ) -> list[Bar]:
        return make_rising_bars(symbol=symbol, n=40)

    def get_latest_quote(self, symbol: str) -> Quote:
        return Quote(
            symbol=symbol,
            timestamp=_SESSION_OPEN,
            bid_price=Decimal(str(self.fill_price - 0.05)),
            bid_size=100,
            ask_price=Decimal(str(self.fill_price + 0.05)),
            ask_size=100,
        )

    def get_latest_price(self, symbol: str) -> Decimal:
        return Decimal(str(self.fill_price))

    def list_assets(self) -> list[Asset]:
        return []

    def get_news(self, symbols: list[str], limit: int = 10) -> list[NewsItem]:
        return []

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
            submitted_at=_SESSION_OPEN,
        )
        self.submitted_orders.append(order)
        return order

    def get_order(self, order_id: str) -> Order:
        for o in self.submitted_orders:
            if o.id == order_id:
                return o.model_copy(
                    update={
                        "status": self.fill_status,
                        "filled_qty": o.qty,
                        "filled_at": _SESSION_OPEN,
                        "filled_avg_price": Decimal(str(self.fill_price)),
                    }
                )
        raise KeyError(f"Order {order_id!r} not found")

    def poll_order(
        self,
        order_id: str,
        timeout_seconds: float = 60.0,
        poll_interval: float = 1.0,
    ) -> Order:
        return self.get_order(order_id)

    def list_positions(self) -> list[Position]:
        return self._positions


def make_bar(
    open_: float,
    high: float,
    low: float,
    close: float,
    volume: int = 100_000,
    symbol: str = "TEST",
    ts: datetime | None = None,
) -> Bar:
    return Bar(
        symbol=symbol,
        timestamp=ts or _SESSION_OPEN,
        open=Decimal(str(open_)),
        high=Decimal(str(high)),
        low=Decimal(str(low)),
        close=Decimal(str(close)),
        volume=volume,
        vwap=Decimal(str((high + low + close) / 3)),
    )


def make_rising_bars(
    n: int = 40,
    start: float = 90.0,
    step: float = 0.5,
    symbol: str = "AAPL",
) -> list[Bar]:
    """
    Strictly rising bars: each candle has higher high than the previous.
    Price is above VWAP by construction (close > open each bar).
    MACD will be bullish after enough bars.
    """
    bars = []
    for i in range(n):
        base = start + i * step
        bars.append(
            make_bar(
                open_=base,
                high=base + step,
                low=base - 0.1,
                close=base + step * 0.8,
                symbol=symbol,
                ts=_SESSION_OPEN + timedelta(minutes=i),
            )
        )
    return bars


def make_falling_bars(
    n: int = 40,
    start: float = 110.0,
    step: float = 0.5,
    symbol: str = "AAPL",
) -> list[Bar]:
    """Strictly falling bars — MACD will be bearish."""
    bars = []
    for i in range(n):
        base = start - i * step
        bars.append(
            make_bar(
                open_=base,
                high=base + 0.1,
                low=base - step,
                close=base - step * 0.8,
                symbol=symbol,
                ts=_SESSION_OPEN + timedelta(minutes=i),
            )
        )
    return bars


def make_flat_bars(
    n: int = 40,
    price: float = 100.0,
    symbol: str = "AAPL",
) -> list[Bar]:
    """Flat/sideways bars."""
    return [
        make_bar(
            price,
            price + 0.1,
            price - 0.1,
            price,
            symbol=symbol,
            ts=_SESSION_OPEN + timedelta(minutes=i),
        )
        for i in range(n)
    ]


def make_accelerating_bars(
    n: int = 40,
    start: float = 90.0,
    symbol: str = "AAPL",
) -> list[Bar]:
    """
    Accelerating uptrend bars (quadratic price growth) so MACD slope is positive.

    Accelerating prices cause the fast EMA to pull away from the slow EMA,
    producing a rising MACD line with positive slope.
    """
    bars = []
    price = start
    for i in range(n):
        # Quadratic increment: each step is larger than the last
        step = 0.1 + i * 0.05
        open_ = price
        close = price + step * 0.8
        high = price + step
        low = price - 0.05
        bars.append(
            make_bar(
                open_,
                high,
                low,
                close,
                symbol=symbol,
                ts=_SESSION_OPEN + timedelta(minutes=i),
            )
        )
        price = close + 0.02
    return bars


def make_breakout_bars(
    base_price: float = 100.0,
    flat_n: int = 30,
    accel_n: int = 15,
    symbol: str = "AAPL",
) -> list[Bar]:
    """
    Flat consolidation followed by an accelerating breakout.

    Designed so ALL entry gate checks pass with default session config
    (overextension_pct=15.0, conviction_threshold=0.6):
    - VWAP ≈ base_price (flat period dominates volume-weighted average)
    - Final price is 5-8% above VWAP → within 15% overextension gate
    - MACD slope is strictly positive (accelerating price → fast EMA pulls away)
    - Each of the last 3 bars has strictly higher high (higher-highs gate)
    - All breakout candles are bullish (bullish_continuation pattern)
    """
    bars: list[Bar] = []
    # Flat period: candles with unique but tiny highs to avoid constant-high issues
    for i in range(flat_n):
        h = base_price + 0.01 + i * 0.0001  # very slowly rising highs
        bars.append(
            make_bar(
                base_price - 0.005,
                h,
                base_price - 0.01,
                base_price + 0.005,
                symbol=symbol,
                ts=_SESSION_OPEN + timedelta(minutes=i),
            )
        )
    # Breakout period: accelerating rise, strictly increasing highs
    price = base_price
    for j in range(accel_n):
        # Step accelerates each bar
        step = base_price * 0.003 * (1.0 + j * 0.2)
        open_ = price
        close = price + step * 0.8
        high = (
            price + step + j * 0.001
        )  # strictly increasing (j factor ensures uniqueness)
        low = price - 0.01
        ts = _SESSION_OPEN + timedelta(minutes=flat_n + j)
        bars.append(make_bar(open_, high, low, close, symbol=symbol, ts=ts))
        price = close
    return bars
