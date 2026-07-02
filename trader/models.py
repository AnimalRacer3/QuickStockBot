"""Shared data structures used across the engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


@dataclass(frozen=True)
class Candle:
    """A single completed 1-minute OHLCV candle."""

    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

    @property
    def is_green(self) -> bool:
        return self.close > self.open

    @property
    def is_red(self) -> bool:
        return self.close < self.open

    @property
    def body(self) -> float:
        return abs(self.close - self.open)

    @property
    def range(self) -> float:
        return self.high - self.low

    @property
    def midpoint(self) -> float:
        return (self.open + self.close) / 2

    @property
    def upper_wick(self) -> float:
        return self.high - max(self.open, self.close)

    @property
    def lower_wick(self) -> float:
        return min(self.open, self.close) - self.low


class ExitReason(str, Enum):
    TAKE_PROFIT = "take_profit"
    STOP_LOSS = "stop_loss"
    TRAIL_OFF = "trail_off"
    VWAP_LOSS = "vwap_loss"
    FORCE_CLOSE = "force_close"
    KILL_SWITCH = "kill_switch"
    GIVEBACK = "giveback"
    MANUAL = "manual"


@dataclass
class WatchlistEntry:
    ticker: str
    reason: str
    catalyst: str
    rank: int
    screen_stats: dict = field(default_factory=dict)


@dataclass
class Position:
    ticker: str
    qty: float
    entry_price: float
    entry_time: datetime
    stop_price: float
    target_price: float
    pattern: str
    pattern_candle_timestamps: list[str]
    scaled_out_pct: float = 0.0
    peak_price: float = 0.0
    order_id: str | None = None

    def __post_init__(self) -> None:
        if self.peak_price <= 0:
            self.peak_price = self.entry_price

    @property
    def remaining_qty(self) -> float:
        return self.qty * (1 - self.scaled_out_pct / 100.0)
