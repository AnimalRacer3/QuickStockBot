"""Helper function tests — no network required."""
from __future__ import annotations

import pytest

from bot.ta.helpers import current_price, high_of_day, low_of_day, vwap
from tests.ta.conftest import make_bar


def _bars():
    return [
        make_bar(10.0, 15.0, 9.0, 11.0, volume=100_000),
        make_bar(11.0, 18.0, 8.5, 14.0, volume=200_000),
        make_bar(14.0, 16.0, 13.0, 13.5, volume=150_000),
    ]


def test_high_of_day():
    assert high_of_day(_bars()) == pytest.approx(18.0)


def test_low_of_day():
    assert low_of_day(_bars()) == pytest.approx(8.5)


def test_current_price():
    bar = make_bar(10.0, 11.0, 9.0, 10.75)
    assert current_price(bar) == pytest.approx(10.75)


def test_vwap_single_bar():
    bar = make_bar(10.0, 12.0, 9.0, 11.0, volume=1_000)
    # typical = (12+9+11)/3 = 10.667; vwap = 10.667
    expected = (12.0 + 9.0 + 11.0) / 3.0
    assert vwap([bar]) == pytest.approx(expected, rel=1e-6)


def test_vwap_multiple_bars():
    bars = [
        make_bar(10.0, 12.0, 9.0, 11.0, volume=100),   # typical=10.667
        make_bar(11.0, 14.0, 10.0, 13.0, volume=200),  # typical=12.333
    ]
    t1 = (12.0 + 9.0 + 11.0) / 3.0
    t2 = (14.0 + 10.0 + 13.0) / 3.0
    expected = (t1 * 100 + t2 * 200) / 300
    assert vwap(bars) == pytest.approx(expected, rel=1e-6)


def test_vwap_zero_volume_fallback():
    bar = make_bar(10.0, 11.0, 9.0, 10.5, volume=0)
    assert vwap([bar]) == pytest.approx(10.5)
