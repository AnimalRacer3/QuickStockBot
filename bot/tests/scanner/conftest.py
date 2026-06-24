"""Shared fixtures for scanner tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional
from unittest.mock import MagicMock

import pytest

from bot.alpaca.client import CalendarDay, ClockInfo, MarketClient
from bot.models import (
    AccountSnapshot,
    Asset,
    Bar,
    NewsItem,
    Order,
    OrderSide,
    OrderType,
    Position,
    Quote,
    TimeInForce,
)
from bot.news.models import ArticleWithSentiment, SentimentScore, TickerSentiment, Article


# ---------------------------------------------------------------------------
# Bar factory
# ---------------------------------------------------------------------------

def make_bar(
    open_: float,
    high: float,
    low: float,
    close: float,
    volume: int = 500_000,
    symbol: str = "TEST",
    ts: Optional[datetime] = None,
) -> Bar:
    return Bar(
        symbol=symbol,
        timestamp=ts or datetime(2024, 1, 2, 9, 30, tzinfo=timezone.utc),
        open=Decimal(str(open_)),
        high=Decimal(str(high)),
        low=Decimal(str(low)),
        close=Decimal(str(close)),
        volume=volume,
    )


def make_bars(n: int = 40, base_price: float = 5.0, symbol: str = "TEST") -> list[Bar]:
    """Make *n* uptrending 1-minute bars for MACD computation."""
    bars = []
    for i in range(n):
        p = base_price + i * 0.05
        bars.append(
            make_bar(
                open_=p,
                high=p + 0.1,
                low=p - 0.05,
                close=p + 0.05,
                volume=500_000,
                symbol=symbol,
                ts=datetime(2024, 1, 2, 9, 30, tzinfo=timezone.utc) + timedelta(minutes=i),
            )
        )
    return bars


# ---------------------------------------------------------------------------
# Sentiment helpers
# ---------------------------------------------------------------------------

def make_positive_sentiment(symbol: str = "TEST") -> TickerSentiment:
    art = ArticleWithSentiment(
        article=Article(
            symbol=symbol,
            headline="Big news",
            summary="Very positive",
            source="test",
            url="http://example.com",
            published_at=datetime(2024, 1, 2, 8, 0, tzinfo=timezone.utc),
        ),
        sentiment=SentimentScore(positive=0.9, negative=0.05, neutral=0.05, score=0.85, label="positive"),
    )
    return TickerSentiment(
        symbol=symbol,
        articles=[art],
        aggregate=SentimentScore(positive=0.9, negative=0.05, neutral=0.05, score=0.85, label="positive"),
    )


def make_neutral_sentiment(symbol: str = "TEST") -> TickerSentiment:
    return TickerSentiment(
        symbol=symbol,
        articles=[],
        aggregate=SentimentScore(positive=0.0, negative=0.0, neutral=1.0, score=0.0, label="neutral"),
    )


# ---------------------------------------------------------------------------
# Mock Alpaca client
# ---------------------------------------------------------------------------

_CLOCK_PAYLOAD = ClockInfo(
    timestamp="2024-01-02T08:30:00-05:00",
    is_open=False,
    next_open="2024-01-02T09:30:00-05:00",
    next_close="2024-01-02T16:00:00-05:00",
)

_CALENDAR_DAY = CalendarDay(date="2024-01-02", open_="09:30", close="16:00")


class FakeScannerClient(MarketClient):
    """Minimal fake for scanner tests — all responses are configurable."""

    def __init__(
        self,
        bars_by_symbol: Optional[dict[str, list[Bar]]] = None,
        prev_bars_by_symbol: Optional[dict[str, list[Bar]]] = None,
        clock: Optional[ClockInfo] = None,
        calendar: Optional[list[CalendarDay]] = None,
        movers: Optional[list[str]] = None,
    ) -> None:
        self._bars = bars_by_symbol or {}
        self._prev_bars = prev_bars_by_symbol or {}
        self._clock = clock or _CLOCK_PAYLOAD
        self._calendar = calendar if calendar is not None else [_CALENDAR_DAY]
        self.movers = movers or []

    # Calendar / clock
    def get_clock(self) -> ClockInfo:
        return self._clock

    def get_calendar(self, start: str, end: str) -> list[CalendarDay]:
        return self._calendar

    # Bars: return intraday bars when timeframe="1Min", daily bars otherwise
    def get_bars(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        timeframe: str = "1Min",
        limit: int = 1000,
    ) -> list[Bar]:
        if timeframe == "1Min":
            return self._bars.get(symbol, [])
        return self._prev_bars.get(symbol, [])

    def get_latest_quote(self, symbol: str) -> Quote:
        raise NotImplementedError

    def get_latest_price(self, symbol: str) -> Decimal:
        raise NotImplementedError

    def list_assets(self) -> list[Asset]:
        return []

    def get_news(self, symbols: list[str], limit: int = 10) -> list[NewsItem]:
        return []

    def submit_order(self, symbol, qty, side, order_type, time_in_force=TimeInForce.DAY, limit_price=None) -> Order:
        raise NotImplementedError

    def get_order(self, order_id: str) -> Order:
        raise NotImplementedError

    def poll_order(self, order_id, timeout_seconds=60.0, poll_interval=1.0) -> Order:
        raise NotImplementedError

    def list_positions(self) -> list[Position]:
        return []

    def get_account(self) -> AccountSnapshot:
        raise NotImplementedError
