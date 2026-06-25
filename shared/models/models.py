"""
Frozen Pydantic v2 data models mirroring /shared/schemas/*.schema.json.
Do not edit by hand — any changes must be reflected in the corresponding JSON Schema.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ─── Enums ────────────────────────────────────────────────────────────────────


class LogLevel(str, Enum):
    debug = "debug"
    info = "info"
    warning = "warning"
    error = "error"


class Broker(str, Enum):
    alpaca = "alpaca"


class OrderType(str, Enum):
    buy = "buy"
    sell = "sell"
    short = "short"
    limit = "limit"


class OrderStatus(str, Enum):
    pending = "pending"
    filled = "filled"
    partial = "partial"
    cancelled = "cancelled"
    rejected = "rejected"


class TradeLabel(str, Enum):
    good = "good"
    bad = "bad"


class LogCategory(str, Enum):
    info = "info"
    warning = "warning"
    error = "error"
    trade = "trade"
    order = "order"
    system = "system"


class DailyPLColor(str, Enum):
    green = "green"
    red = "red"
    blue = "blue"


class TickerRole(str, Enum):
    leader = "leader"
    laggard = "laggard"
    standalone = "standalone"


class RpcMethodName(str, Enum):
    get_state = "get_state"
    get_active_tickers = "get_active_tickers"
    get_ticker_detail = "get_ticker_detail"
    get_settings = "get_settings"
    update_settings = "update_settings"
    get_lists = "get_lists"
    update_lists = "update_lists"
    get_trade_history = "get_trade_history"
    get_order_detail = "get_order_detail"
    subscribe_logs = "subscribe_logs"
    get_daily_pl = "get_daily_pl"


# ─── Settings ─────────────────────────────────────────────────────────────────


class Settings(BaseModel):
    bot_id: str
    relay_url: str
    license_key: str
    connection_password: str | None = None
    paper_trading: bool = True
    broker: Broker = Broker.alpaca
    broker_api_key: str | None = None
    broker_api_secret: str | None = None
    watchlist: list[str] = Field(default_factory=list)
    blacklist: list[str] = Field(default_factory=list)
    max_positions: int = Field(default=5, ge=1, le=50)
    risk_per_trade_pct: float = Field(default=1.0, ge=0.1, le=10.0)
    daily_risk_pct: float = Field(default=5.0, ge=0.1, le=100.0)
    risk_override_enabled: bool = False
    goal_post_trade_count: int | None = Field(default=None, ge=1)
    min_score: float = Field(default=60.0, ge=0, le=100)
    auto_trade: bool = False
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    log_level: LogLevel = LogLevel.info


# ─── TickerState ──────────────────────────────────────────────────────────────


class TickerState(BaseModel):
    symbol: str
    last_price: float = Field(ge=0)
    high_of_day: float = Field(ge=0)
    low_of_day: float = Field(ge=0)
    macd_line: float
    macd_signal: float
    macd_hist: float
    pattern_tags: list[str] = Field(default_factory=list)
    score: float = Field(ge=0, le=100)
    updated_at: datetime
    # Section 8 extended fields
    float_shares: int | None = None
    unknown_float: bool | None = None
    tradable: bool | None = None
    rvol: float | None = None
    pct_change: float | None = None
    macd_favorability: float | None = Field(default=None, ge=-1.0, le=1.0)
    macd_eligible: bool | None = None
    role: TickerRole | None = None


# ─── Order ────────────────────────────────────────────────────────────────────


class Order(BaseModel):
    id: str
    type: OrderType
    symbol: str
    qty: float = Field(ge=0)
    submitted_price: float = Field(ge=0)
    status: OrderStatus
    filled_qty: float | None = Field(default=None, ge=0)
    filled_price: float | None = Field(default=None, ge=0)
    submitted_at: datetime | None = None
    updated_at: datetime | None = None


# ─── OrderStatusEvent ─────────────────────────────────────────────────────────


class OrderStatusEvent(BaseModel):
    order_id: str
    status: OrderStatus
    timestamp: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
    filled_qty: float | None = Field(default=None, ge=0)
    filled_price: float | None = Field(default=None, ge=0)


# ─── Trade ────────────────────────────────────────────────────────────────────


class Trade(BaseModel):
    id: str
    symbol: str
    entry_order: Order
    exit_order: Order
    net_pl: float
    label: TradeLabel
    opened_at: datetime | None = None
    closed_at: datetime | None = None


# ─── LogEvent ─────────────────────────────────────────────────────────────────


class LogEvent(BaseModel):
    timestamp: datetime
    category: LogCategory
    message: str
    payload: dict[str, Any] | None = None


# ─── AccountSnapshot ──────────────────────────────────────────────────────────


class AccountSnapshot(BaseModel):
    buying_power: float = Field(ge=0)
    equity: float = Field(ge=0)
    pdt_flag: bool
    pdt_trades_remaining: int | None = Field(default=None, ge=0)
    open_positions: int | None = Field(default=None, ge=0)
    snapshot_at: datetime


# ─── Daily P/L ────────────────────────────────────────────────────────────────


class DailyPLEntry(BaseModel):
    date: str
    ran: bool
    net_pl: float
    trade_count: int = Field(ge=0)
    color: DailyPLColor


class DailyPLResult(BaseModel):
    days: list[DailyPLEntry]


# ─── Relay Protocol ───────────────────────────────────────────────────────────


class Envelope(BaseModel):
    type: str
    id: str
    payload: dict[str, Any]


class RegisterPayload(BaseModel):
    bot_id: str
    license_key: str
    connection_password_proof: str
    version: str


class StateUpdatePayload(BaseModel):
    tickers: list[TickerState]
    account: AccountSnapshot | None = None


class RpcError(BaseModel):
    code: str
    message: str


class RpcResponsePayload(BaseModel):
    result: Any
    error: RpcError | None = None


class AuthChallengePayload(BaseModel):
    nonce: str


class RpcRequestPayload(BaseModel):
    method: RpcMethodName
    params: dict[str, Any] | None = None
