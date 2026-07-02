from tests.fixtures import candle_builders as fx
from trader import patterns


def test_morning_star_positive():
    assert patterns.detect_morning_star(fx.morning_star_positive()) is not None


def test_morning_star_negative_weak_reversal():
    assert patterns.detect_morning_star(fx.morning_star_negative_weak_reversal()) is None


def test_three_white_soldiers_positive():
    assert patterns.detect_three_white_soldiers(fx.three_white_soldiers_positive()) is not None


def test_three_white_soldiers_negative_long_wick():
    assert patterns.detect_three_white_soldiers(fx.three_white_soldiers_negative_long_wick()) is None


def test_rising_three_methods_positive():
    assert patterns.detect_rising_three_methods(fx.rising_three_methods_positive()) is not None


def test_rising_three_methods_negative_no_new_high():
    assert patterns.detect_rising_three_methods(fx.rising_three_methods_negative_no_new_high()) is None


def test_pullback_positive():
    candles, vwap_values = fx.pullback_positive()
    match = patterns.detect_pullback(candles, vwap_values)
    assert match is not None
    assert match.pattern == "pullback"


def test_pullback_negative_no_new_high():
    candles, vwap_values = fx.pullback_negative_no_new_high()
    assert patterns.detect_pullback(candles, vwap_values) is None


def test_breakout_base_positive():
    assert patterns.detect_breakout_base(fx.breakout_base_positive()) is not None


def test_breakout_base_negative_low_volume():
    assert patterns.detect_breakout_base(fx.breakout_base_negative_low_volume()) is None


def test_no_pattern_from_too_few_candles():
    short = fx.morning_star_positive()[:2]
    assert patterns.detect_morning_star(short) is None
    assert patterns.detect_three_white_soldiers(short) is None
    assert patterns.detect_rising_three_methods(short) is None
    assert patterns.detect_breakout_base(short) is None


def test_detect_all_respects_toggles():
    candles = fx.morning_star_positive()
    enabled = {"morning_star": False, "three_white_soldiers": False, "rising_three_methods": False, "pullback": False, "breakout_base": False}
    assert patterns.detect_all(candles, enabled) == []

    enabled["morning_star"] = True
    matches = patterns.detect_all(candles, enabled)
    assert len(matches) == 1
    assert matches[0].pattern == "morning_star"
