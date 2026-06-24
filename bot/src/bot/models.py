from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"


class OrderStatus(str, Enum):
    NEW = "new"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    DONE_FOR_DAY = "done_for_day"
    CANCELED = "canceled"
    EXPIRED = "expired"
    REPLACED = "replaced"
    PENDING_CANCEL = "pending_cancel"
    PENDING_REPLACE = "pending_replace"
    HELD = "held"
    ACCEPTED = "accepted"
    PENDING_NEW = "pending_new"
    ACCEPTED_FOR_BIDDING = "accepted_for_bidding"
    STOPPED = "stopped"
    REJECTED = "rejected"
    SUSPENDED = "suspended"
    CALCULATED = "calculated"


class TimeInForce(str, Enum):
    DAY = "day"
    GTC = "gtc"
    OPG = "opg"
    CLS = "cls"
    IOC = "ioc"
    FOK = "fok"


class Bar(BaseModel):
    symbol: str
    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    vwap: Optional[Decimal] = None
    trade_count: Optional[int] = None
    timeframe: str = "1Min"


class Quote(BaseModel):
    symbol: str
    timestamp: datetime
    bid_price: Decimal
    bid_size: int
    ask_price: Decimal
    ask_size: int

    @property
    def mid_price(self) -> Decimal:
        return (self.bid_price + self.ask_price) / Decimal("2")


class Asset(BaseModel):
    id: str
    symbol: str
    name: str
    exchange: str
    asset_class: str
    tradable: bool
    marginable: bool
    shortable: bool
    easy_to_borrow: bool
    fractionable: bool


class NewsItem(BaseModel):
    id: int
    headline: str
    summary: str
    author: str
    created_at: datetime
    updated_at: datetime
    url: str
    symbols: list[str]
    source: str


class Order(BaseModel):
    id: str
    client_order_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    qty: Decimal
    filled_qty: Decimal = Decimal("0")
    limit_price: Optional[Decimal] = None
    status: OrderStatus
    time_in_force: TimeInForce
    submitted_at: datetime
    filled_at: Optional[datetime] = None
    canceled_at: Optional[datetime] = None
    expired_at: Optional[datetime] = None
    filled_avg_price: Optional[Decimal] = None


class Position(BaseModel):
    symbol: str
    qty: Decimal
    avg_entry_price: Decimal
    market_value: Decimal
    unrealized_pl: Decimal
    unrealized_plpc: Decimal
    current_price: Decimal
    side: str


class AccountSnapshot(BaseModel):
    buying_power: Decimal
    equity: Decimal
    cash: Decimal
    portfolio_value: Decimal
    pattern_day_trader: bool
    day_trade_count: int
    day_trading_buying_power: Decimal
    is_pdt_restricted: bool = Field(
        description="True when account is flagged PDT and equity < $25k"
    )
