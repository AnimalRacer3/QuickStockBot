from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from bot.models import Bar


def make_bar(
    open_: float,
    high: float,
    low: float,
    close: float,
    volume: int = 100_000,
    symbol: str = "TEST",
) -> Bar:
    return Bar(
        symbol=symbol,
        timestamp=datetime(2024, 1, 2, 9, 30),
        open=Decimal(str(open_)),
        high=Decimal(str(high)),
        low=Decimal(str(low)),
        close=Decimal(str(close)),
        volume=volume,
    )
