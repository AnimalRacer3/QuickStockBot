"""Reusable candle-fixture builders for pattern detector tests."""

from __future__ import annotations

from datetime import datetime, timedelta

from trader.models import Candle

_BASE_TIME = datetime(2024, 1, 2, 9, 30)


def candle(minute_offset: int, o: float, h: float, l: float, c: float, v: float) -> Candle:
    return Candle(timestamp=_BASE_TIME + timedelta(minutes=minute_offset), open=o, high=h, low=l, close=c, volume=v)


def morning_star_positive() -> list[Candle]:
    return [
        candle(0, 10.0, 10.1, 8.8, 9.0, 1000),
        candle(1, 8.95, 8.95, 8.7, 8.9, 500),
        candle(2, 8.9, 9.75, 8.85, 9.7, 800),
    ]


def morning_star_negative_weak_reversal() -> list[Candle]:
    # c2 fails to close above c0's midpoint (9.5)
    return [
        candle(0, 10.0, 10.1, 8.8, 9.0, 1000),
        candle(1, 8.95, 8.95, 8.7, 8.9, 500),
        candle(2, 8.9, 9.3, 8.85, 9.3, 800),
    ]


def three_white_soldiers_positive() -> list[Candle]:
    return [
        candle(0, 10.0, 10.55, 9.95, 10.5, 1000),
        candle(1, 10.2, 10.95, 10.15, 10.9, 1100),
        candle(2, 10.6, 11.35, 10.55, 11.3, 1050),
    ]


def three_white_soldiers_negative_long_wick() -> list[Candle]:
    return [
        candle(0, 10.0, 10.55, 9.95, 10.5, 1000),
        candle(1, 10.2, 10.95, 10.15, 10.9, 1100),
        candle(2, 10.6, 12.0, 10.55, 11.3, 1050),  # huge upper wick
    ]


def rising_three_methods_positive() -> list[Candle]:
    return [
        candle(0, 10.0, 11.05, 9.95, 11.0, 5000),
        candle(1, 10.9, 11.0, 10.7, 10.8, 800),
        candle(2, 10.8, 10.95, 10.75, 10.85, 700),
        candle(3, 10.85, 10.95, 10.6, 10.75, 750),
        candle(4, 10.75, 11.35, 10.7, 11.3, 1600),
    ]


def rising_three_methods_negative_no_new_high() -> list[Candle]:
    return [
        candle(0, 10.0, 11.05, 9.95, 11.0, 5000),
        candle(1, 10.9, 11.0, 10.7, 10.8, 800),
        candle(2, 10.8, 10.95, 10.75, 10.85, 700),
        candle(3, 10.85, 10.95, 10.6, 10.75, 750),
        candle(4, 10.75, 11.0, 10.7, 11.0, 1600),  # doesn't clear c0.high (11.05)
    ]


def pullback_positive() -> tuple[list[Candle], list[float]]:
    candles = [
        candle(0, 10.0, 10.85, 9.95, 10.8, 2000),  # surge
        candle(1, 10.8, 10.82, 10.55, 10.6, 1500),  # pullback 1
        candle(2, 10.6, 10.65, 10.45, 10.5, 1200),  # pullback 2
        candle(3, 10.5, 10.6, 10.42, 10.55, 1000),  # pullback 3
        candle(4, 10.55, 10.95, 10.5, 10.9, 1300),  # breakout
    ]
    vwap_values = [10.0, 10.0, 10.0, 10.0, 10.0]
    return candles, vwap_values


def pullback_negative_no_new_high() -> tuple[list[Candle], list[float]]:
    candles = [
        candle(0, 10.0, 10.85, 9.95, 10.8, 2000),
        candle(1, 10.8, 10.82, 10.55, 10.6, 1500),
        candle(2, 10.6, 10.65, 10.45, 10.5, 1200),
        candle(3, 10.5, 10.6, 10.42, 10.55, 1000),
        candle(4, 10.55, 10.55, 10.5, 10.5, 1300),  # never exceeds prior pullback high (10.6)
    ]
    vwap_values = [10.0, 10.0, 10.0, 10.0, 10.0]
    return candles, vwap_values


def breakout_base_positive() -> list[Candle]:
    return [
        candle(0, 19.95, 20.05, 19.90, 20.0, 2000),
        candle(1, 20.0, 20.03, 19.92, 19.98, 1500),
        candle(2, 19.98, 20.02, 19.93, 20.0, 1000),
        candle(3, 20.0, 20.55, 19.99, 20.5, 3500),  # breakout
    ]


def breakout_base_negative_low_volume() -> list[Candle]:
    return [
        candle(0, 19.95, 20.05, 19.90, 20.0, 2000),
        candle(1, 20.0, 20.03, 19.92, 19.98, 1500),
        candle(2, 19.98, 20.02, 19.93, 20.0, 1000),
        candle(3, 20.0, 20.55, 19.99, 20.5, 2000),  # breakout volume < 2x base avg under any window size
    ]
