from datetime import datetime, timedelta

import pytest

from trader import risk
from trader.models import Candle, ExitReason, Position


def _candle(o, h, l, c, v=1000, minute=0):
    return Candle(timestamp=datetime(2024, 1, 2, 9, 30) + timedelta(minutes=minute), open=o, high=h, low=l, close=c, volume=v)


def test_position_size_risk_limited():
    # $100 equity risk at 2%, $2 risk/share (1% of $200 price) -> 2/2 = 1 share by risk;
    # buying power cap is generous so risk should bind.
    qty = risk.position_size(
        equity=10_000, buying_power=50_000, price=200.0,
        risk_per_trade_pct=2, stop_loss_pct=1, max_position_pct_bp=100,
    )
    # risk_amount = 200, risk_per_share = 2.0 -> qty_by_risk = 100
    # max_position_value = 50000, qty_by_position_cap = 250
    assert qty == 100


def test_position_size_buying_power_limited():
    qty = risk.position_size(
        equity=100_000, buying_power=1_000, price=50.0,
        risk_per_trade_pct=2, stop_loss_pct=1, max_position_pct_bp=25,
    )
    # max_position_value = 250, qty_by_position_cap = 5; risk cap would allow much more
    assert qty == 5


def test_position_size_zero_on_bad_inputs():
    assert risk.position_size(0, 1000, 10, 2, 1, 25) == 0
    assert risk.position_size(1000, 0, 10, 2, 1, 25) == 0
    assert risk.position_size(1000, 1000, 0, 2, 1, 25) == 0


def test_stop_and_target_prices():
    assert risk.stop_price(100.0, 1.0) == 99.0
    assert risk.target_price(100.0, 3.0) == 103.0
    assert risk.trail_off_trigger_price(100.0, 1.5) == pytest.approx(101.5)


def test_next_scale_out_pct_caps_at_100():
    assert risk.next_scale_out_pct(0, 25) == 25
    assert risk.next_scale_out_pct(90, 25) == 100


def test_kill_switch_triggers_at_threshold():
    assert risk.kill_switch_triggered(10_000, 9_000, -10) is True  # exactly -10%
    assert risk.kill_switch_triggered(10_000, 9_001, -10) is False
    assert risk.kill_switch_triggered(10_000, 8_000, -10) is True


def test_profit_giveback_ignores_red_days():
    # never went green -> never triggers regardless of current drawdown
    assert risk.profit_giveback_triggered(10_000, 10_000, 9_000, 25) is False
    assert risk.profit_giveback_triggered(10_000, 9_500, 9_000, 25) is False


def test_profit_giveback_triggers_on_giveback_from_peak():
    # peak gain = 1000; giving back 25% of that (250) from the peak triggers
    assert risk.profit_giveback_triggered(10_000, 11_000, 10_750, 25) is True
    assert risk.profit_giveback_triggered(10_000, 11_000, 10_800, 25) is False


def test_no_trade_cutoff():
    market_open = datetime(2024, 1, 2, 9, 30)
    before_cutoff = market_open + timedelta(hours=1, minutes=59)
    at_cutoff = market_open + timedelta(hours=2)
    assert risk.no_trade_cutoff_triggered(before_cutoff, market_open, 2, entries_made=0) is False
    assert risk.no_trade_cutoff_triggered(at_cutoff, market_open, 2, entries_made=0) is True
    assert risk.no_trade_cutoff_triggered(at_cutoff, market_open, 2, entries_made=1) is False


def _make_position(entry_price=100.0):
    return Position(
        ticker="TEST", qty=100, entry_price=entry_price, entry_time=datetime(2024, 1, 2, 9, 31),
        stop_price=risk.stop_price(entry_price, 1.0), target_price=risk.target_price(entry_price, 3.0),
        pattern="morning_star", pattern_candle_timestamps=[],
    )


_RISK_CFG = risk.RiskConfig(
    stop_loss_pct=1.0, take_profit_pct=3.0, trail_off_trigger_pct=1.5, trail_off_scale_out_pct=25.0, overextension_pct=3.0
)


def test_evaluate_exit_take_profit_has_priority():
    position = _make_position(100.0)
    position.peak_price = 103.5  # would also satisfy trail-off
    candle = _candle(o=103.0, h=103.5, l=102.8, c=103.2, minute=5)
    reason, pct = risk.evaluate_exit(position, candle, vwap_value=100.0, volume_confirmed_on_candle=True, cfg=_RISK_CFG)
    # candle high 103.5 >= target 103.0 -> take-profit wins over trail-off
    assert reason == ExitReason.TAKE_PROFIT
    assert pct == 100.0


def test_evaluate_exit_stop_loss():
    position = _make_position(100.0)
    candle = _candle(o=99.5, h=99.6, l=98.9, c=99.0, minute=3)
    reason, pct = risk.evaluate_exit(position, candle, vwap_value=99.0, volume_confirmed_on_candle=False, cfg=_RISK_CFG)
    assert reason == ExitReason.STOP_LOSS
    assert pct == 100.0


def test_evaluate_exit_trail_off_on_red_candle_after_trigger():
    position = _make_position(100.0)
    position.peak_price = 102.0  # above the 1.5% trigger (101.5)
    candle = _candle(o=101.8, h=101.9, l=101.5, c=101.6, minute=10)  # red candle, no stop/target hit
    reason, pct = risk.evaluate_exit(position, candle, vwap_value=100.5, volume_confirmed_on_candle=False, cfg=_RISK_CFG)
    assert reason == ExitReason.TRAIL_OFF
    assert pct == 25.0


def test_evaluate_exit_vwap_loss_with_volume():
    position = _make_position(100.0)
    candle = _candle(o=100.2, h=100.3, l=99.8, c=99.9, minute=7)  # below VWAP, no stop/target hit
    reason, pct = risk.evaluate_exit(position, candle, vwap_value=100.0, volume_confirmed_on_candle=True, cfg=_RISK_CFG)
    assert reason == ExitReason.VWAP_LOSS
    assert pct == 100.0


def test_evaluate_exit_no_trigger():
    position = _make_position(100.0)
    candle = _candle(o=100.2, h=100.4, l=100.0, c=100.3, minute=2)
    reason, pct = risk.evaluate_exit(position, candle, vwap_value=100.0, volume_confirmed_on_candle=False, cfg=_RISK_CFG)
    assert reason is None
    assert pct == 0.0
