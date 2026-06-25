"""Exit mode tests — Section 6: dump vs trail_off."""

from __future__ import annotations

from bot.engine.exits import (
    OpenPosition,
    check_take_profit,
    check_trailing_stop,
    dump_exit,
    trail_off_candle_pattern,
    trail_off_per_candle,
    update_high_water_mark,
)
from bot.ta.models import MacdState


def _pos(
    symbol: str = "AAPL",
    entry: float = 100.0,
    shares: int = 100,
    remaining: int | None = None,
    hwm: float | None = None,
) -> OpenPosition:
    remaining = remaining if remaining is not None else shares
    hwm = hwm if hwm is not None else entry
    return OpenPosition(
        symbol=symbol,
        entry_price=entry,
        shares=shares,
        remaining_shares=remaining,
        high_water_mark=hwm,
    )


def _macd(eligible: bool = True, slope: float = 0.1) -> MacdState:
    return MacdState(value=1.0, slope=slope, hist=0.05, favorability=0.7, eligible=eligible)


_BULLISH = frozenset(["bullish_engulfing", "hammer", "morning_star", "bullish_continuation"])


class TestTakeProfit:
    def test_hit(self) -> None:
        pos = _pos(entry=100.0)
        assert check_take_profit(pos, current_price=103.01, take_profit_pct=3.0)

    def test_not_hit(self) -> None:
        pos = _pos(entry=100.0)
        assert not check_take_profit(pos, current_price=102.99, take_profit_pct=3.0)

    def test_exact_target(self) -> None:
        pos = _pos(entry=100.0)
        assert check_take_profit(pos, current_price=103.0, take_profit_pct=3.0)


class TestTrailingStop:
    def test_hit_after_high(self) -> None:
        pos = _pos(entry=100.0, hwm=110.0)
        # stop = 110 * 0.99 = 108.9
        assert check_trailing_stop(pos, current_price=108.0, trailing_stop_pct=1.0)

    def test_not_hit(self) -> None:
        pos = _pos(entry=100.0, hwm=110.0)
        assert not check_trailing_stop(pos, current_price=110.0, trailing_stop_pct=1.0)

    def test_hwm_updates(self) -> None:
        pos = _pos(entry=100.0, hwm=100.0)
        update_high_water_mark(pos, 115.0)
        assert pos.high_water_mark == 115.0
        update_high_water_mark(pos, 112.0)  # should not lower HWM
        assert pos.high_water_mark == 115.0


class TestDumpExit:
    def test_dumps_all_remaining(self) -> None:
        pos = _pos(shares=100, remaining=75)
        sig = dump_exit(pos, "take_profit")
        assert sig.shares_to_sell == 75
        assert sig.is_final

    def test_full_position(self) -> None:
        pos = _pos(shares=100, remaining=100)
        sig = dump_exit(pos, "max_loss")
        assert sig.shares_to_sell == 100
        assert sig.is_final


class TestTrailOffPerCandle:
    def test_scale_out_fraction_while_bullish(self) -> None:
        pos = _pos(shares=100, remaining=100)
        macd = _macd(eligible=True, slope=0.1)
        sig = trail_off_per_candle(
            pos, macd, ["bullish_continuation"], _BULLISH, fraction=0.25
        )
        assert sig is not None
        assert sig.shares_to_sell == 25  # floor(100 * 0.25)
        assert not sig.is_final

    def test_dump_remainder_when_not_bullish(self) -> None:
        pos = _pos(shares=100, remaining=60)
        macd = _macd(eligible=False, slope=-0.1)  # not bullish
        sig = trail_off_per_candle(
            pos, macd, [], _BULLISH, fraction=0.25
        )
        assert sig is not None
        assert sig.is_final
        assert sig.shares_to_sell == 60  # dump all remaining

    def test_dump_on_reversal_tag(self) -> None:
        pos = _pos(shares=100, remaining=80)
        macd = _macd(eligible=True, slope=0.1)
        sig = trail_off_per_candle(
            pos, macd, ["bullish_continuation", "bearish_engulfing"], _BULLISH, fraction=0.25
        )
        assert sig is not None
        assert sig.is_final  # bearish tag → dump remainder

    def test_fractional_sell_rounds_up_to_1(self) -> None:
        pos = _pos(shares=3, remaining=3)
        macd = _macd(eligible=True, slope=0.1)
        sig = trail_off_per_candle(
            pos, macd, ["bullish_continuation"], _BULLISH, fraction=0.1
        )
        assert sig is not None
        assert sig.shares_to_sell >= 1

    def test_final_when_fraction_covers_remaining(self) -> None:
        pos = _pos(shares=4, remaining=4)
        macd = _macd(eligible=True, slope=0.1)
        sig = trail_off_per_candle(
            pos, macd, ["bullish_continuation"], _BULLISH, fraction=0.5
        )
        # floor(4 * 0.5) = 2, not final
        assert sig is not None
        assert not sig.is_final
        assert sig.shares_to_sell == 2


class TestTrailOffCandlePattern:
    def test_sell_on_new_pattern_confirmation(self) -> None:
        pos = _pos(shares=100, remaining=100)
        macd = _macd(eligible=True, slope=0.1)
        prev_tags: list[str] = ["bullish_continuation"]
        new_tags = ["bullish_continuation", "hammer"]  # new: hammer
        sig = trail_off_candle_pattern(
            pos, macd, new_tags, _BULLISH, prev_tags, fraction=0.25
        )
        assert sig is not None
        assert sig.shares_to_sell == 25

    def test_no_new_pattern_hold(self) -> None:
        pos = _pos(shares=100, remaining=100)
        macd = _macd(eligible=True, slope=0.1)
        prev_tags = ["bullish_continuation"]
        same_tags = ["bullish_continuation"]
        sig = trail_off_candle_pattern(
            pos, macd, same_tags, _BULLISH, prev_tags, fraction=0.25
        )
        assert sig is None  # no new confirmation → hold

    def test_dump_on_reversal(self) -> None:
        pos = _pos(shares=100, remaining=80)
        macd = _macd(eligible=True, slope=0.1)
        prev_tags: list[str] = ["bullish_continuation"]
        tags_with_reversal = ["bullish_continuation", "bearish_engulfing"]
        sig = trail_off_candle_pattern(
            pos, macd, tags_with_reversal, _BULLISH, prev_tags, fraction=0.25
        )
        assert sig is not None
        assert sig.is_final
        assert sig.shares_to_sell == 80
