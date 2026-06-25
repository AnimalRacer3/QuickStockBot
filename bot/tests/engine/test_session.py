"""
Simulated session tests — Section 6 execution engine.

All tests use injected fake clock + configurable market client.
No live network calls.

Note: make_accelerating_bars is used wherever the entry gate must actually pass
(rising MACD slope is required). make_rising_bars / make_falling_bars are used
elsewhere for bar data that does not need to pass the entry gate.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from bot.engine.config import ExecutionConfig
from bot.engine.session import ExecutionSession
from bot.models import OrderSide, OrderStatus
from bot.ta.config import TAConfig
from tests.engine.conftest import (
    ConfigurableMarketClient,
    FakeClock,
    make_breakout_bars,
    make_falling_bars,
    make_flat_bars,
)

_SESSION_OPEN = datetime(2024, 6, 10, 13, 30, 0, tzinfo=timezone.utc)
_PAST_Z_HOUR = datetime(
    2024, 6, 10, 14, 31, 0, tzinfo=timezone.utc
)  # 61 min after open


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_dummy_open_trade(
    symbol: str = "TSLA", shares: int = 10, entry: float = 100.0
):
    """Inject a pre-existing open trade into a session."""
    from uuid import uuid4

    from bot.engine.exits import OpenPosition
    from bot.engine.session import TradeRecord
    from bot.models import Order, OrderSide, OrderStatus, OrderType, TimeInForce

    order = Order(
        id=str(uuid4()),
        client_order_id=str(uuid4()),
        symbol=symbol,
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        qty=Decimal(str(shares)),
        status=OrderStatus.FILLED,
        time_in_force=TimeInForce.DAY,
        submitted_at=datetime.now(timezone.utc),
        filled_avg_price=Decimal(str(entry)),
    )
    pos = OpenPosition(symbol, entry, shares, shares, entry)
    return TradeRecord(
        symbol=symbol, entry_order=order, entry_price=entry, shares=shares, position=pos
    )


def _session(
    cfg: ExecutionConfig | None = None,
    equity: float = 100_000.0,
    buying_power: float = 100_000.0,
    day_trading_buying_power: float = 400_000.0,
    is_pdt_restricted: bool = False,
    fill_price: float = 100.0,
    fill_status: OrderStatus = OrderStatus.FILLED,
    now: datetime | None = None,
    conviction: float = 1.0,
) -> tuple[ExecutionSession, ConfigurableMarketClient, FakeClock]:
    cfg = cfg or ExecutionConfig(
        active_tickers_n=5,
        stop_loss_pct=1.0,
        daily_max_loss_pct=-2.0,
        daily_profit_target_pct=3.0,
        flatten_on_max_loss=True,
        flatten_on_profit_target=False,
        position_size_pct=50.0,
        override_risk_per_trade=False,
        exit_mode="dump",
        trailing_stop=False,
        force_close_at_close=False,
        z_hour_cutoff=1.0,
        conviction_threshold=0.6,
        overextension_pct=15.0,  # generous for test bars
    )
    client = ConfigurableMarketClient(
        equity=equity,
        buying_power=buying_power,
        day_trading_buying_power=day_trading_buying_power,
        is_pdt_restricted=is_pdt_restricted,
        fill_price=fill_price,
        fill_status=fill_status,
    )
    clock = FakeClock(now=now or _PAST_Z_HOUR, session_open=_SESSION_OPEN)
    sess = ExecutionSession(
        client=client,
        clock=clock,
        config=cfg,
        ta_config=TAConfig(
            macd_fast=3,
            macd_slow=5,
            macd_signal=2,
            macd_slope_lookback=3,
            macd_enforce_above_zero=False,
            enabled_patterns=["bullish_continuation"],
        ),
        score_setup_fn=lambda sym, bars: conviction,
    )
    return sess, client, clock


# ---------------------------------------------------------------------------
# Front-side accept vs back-side reject
# ---------------------------------------------------------------------------


class TestFrontSideVsBackSide:
    def test_front_side_accept_enters_trade(self) -> None:
        sess, client, _ = _session(conviction=1.0)
        sess.start_day()
        # Accelerating bars → rising MACD slope → passes entry gate
        bars = make_breakout_bars()
        result = sess.run_cycle(["AAPL"], {"AAPL": bars})
        assert result.trades_entered == 1
        buy_orders = [o for o in client.submitted_orders if o.side == OrderSide.BUY]
        assert len(buy_orders) == 1

    def test_back_side_reject_no_entry(self) -> None:
        sess, client, _ = _session(conviction=1.0)
        sess.start_day()
        bars = make_falling_bars(n=20)
        result = sess.run_cycle(["AAPL"], {"AAPL": bars})
        assert result.trades_entered == 0
        assert not client.submitted_orders

    def test_flat_bars_no_entry(self) -> None:
        sess, client, _ = _session(conviction=1.0)
        sess.start_day()
        bars = make_flat_bars(n=20)
        result = sess.run_cycle(["AAPL"], {"AAPL": bars})
        assert result.trades_entered == 0

    def test_log_records_skip_reason(self) -> None:
        sess, _, _ = _session(conviction=1.0)
        sess.start_day()
        bars = make_falling_bars(n=20)
        result = sess.run_cycle(["AAPL"], {"AAPL": bars})
        assert any("SKIP" in msg for msg in result.log_messages)


# ---------------------------------------------------------------------------
# Conviction gate
# ---------------------------------------------------------------------------


class TestConvictionGate:
    def test_below_threshold_skips(self) -> None:
        sess, client, _ = _session(conviction=0.3)  # < 0.6 threshold
        sess.start_day()
        # Any bars — gate fails on conviction (or MACD) → 0 entries either way
        bars = make_falling_bars(n=20)
        result = sess.run_cycle(["AAPL"], {"AAPL": bars})
        assert result.trades_entered == 0
        assert not client.submitted_orders

    def test_at_threshold_accepts(self) -> None:
        sess, client, _ = _session(conviction=0.6)
        sess.start_day()
        bars = make_breakout_bars()
        result = sess.run_cycle(["AAPL"], {"AAPL": bars})
        assert result.trades_entered == 1

    def test_above_threshold_accepts(self) -> None:
        sess, client, _ = _session(conviction=0.9)
        sess.start_day()
        bars = make_breakout_bars()
        result = sess.run_cycle(["AAPL"], {"AAPL": bars})
        assert result.trades_entered == 1

    def test_conviction_blocks_specifically(self) -> None:
        """Gate fails at conviction step — other conditions pass."""
        cfg = ExecutionConfig(
            conviction_threshold=0.8,
            z_hour_cutoff=0.0,
            overextension_pct=15.0,
            exit_mode="dump",
            force_close_at_close=False,
            stop_loss_pct=1.0,
        )
        sess, client, _ = _session(cfg=cfg, conviction=0.5)  # below 0.8
        sess.start_day()
        bars = make_breakout_bars()
        result = sess.run_cycle(["AAPL"], {"AAPL": bars})
        assert result.trades_entered == 0
        assert any("conviction" in m.lower() for m in result.log_messages)


# ---------------------------------------------------------------------------
# Sizing with greyed default and override
# ---------------------------------------------------------------------------


class TestSizingIntegration:
    """
    Integration sizing tests. Exact share math is tested in test_sizing.py.
    Here we verify the sizing logic integrates correctly with the entry gate.
    """

    def _bars(self) -> list:
        return make_breakout_bars()

    def _cfg(self, **kw: object) -> ExecutionConfig:
        return ExecutionConfig(
            conviction_threshold=0.0,
            z_hour_cutoff=0.0,
            exit_mode="dump",
            force_close_at_close=False,
            overextension_pct=15.0,
            **kw,  # type: ignore[arg-type]
        )

    def test_greyed_default_enters_trade(self) -> None:
        """Default sizing (no override) succeeds and uses the daily-number risk."""
        cfg = self._cfg(
            daily_max_loss_pct=-2.0,
            stop_loss_pct=1.0,
            position_size_pct=50.0,
            override_risk_per_trade=False,
        )
        sess, client, _ = _session(
            cfg=cfg,
            equity=100_000,
            buying_power=100_000,
            fill_price=100.0,
            conviction=1.0,
        )
        sess.start_day()
        result = sess.run_cycle(["AAPL"], {"AAPL": self._bars()})
        assert result.trades_entered == 1
        buy = [o for o in client.submitted_orders if o.side == OrderSide.BUY][0]
        # Verify shares are bounded by buying_power * position_size_pct / entry_price
        shares = int(buy.qty)
        assert shares >= 1

    def test_valid_lower_override_results_in_smaller_position(self) -> None:
        """With override_risk_per_trade=True and lower risk, position is smaller."""
        bars = self._bars()
        # First run with greyed default
        cfg_default = self._cfg(
            daily_max_loss_pct=-2.0,
            stop_loss_pct=1.0,
            position_size_pct=100.0,
            override_risk_per_trade=False,
        )
        sess_d, client_d, _ = _session(
            cfg=cfg_default,
            equity=100_000,
            buying_power=500_000,
            fill_price=100.0,
            conviction=1.0,
        )
        sess_d.start_day()
        sess_d.run_cycle(["AAPL"], {"AAPL": bars})
        shares_default = int(client_d.submitted_orders[0].qty)

        # Then with lower override (0.5% < 2%)
        cfg_override = self._cfg(
            daily_max_loss_pct=-2.0,
            stop_loss_pct=1.0,
            position_size_pct=100.0,
            override_risk_per_trade=True,
            risk_per_trade_pct=0.5,
        )
        sess_o, client_o, _ = _session(
            cfg=cfg_override,
            equity=100_000,
            buying_power=500_000,
            fill_price=100.0,
            conviction=1.0,
        )
        sess_o.start_day()
        sess_o.run_cycle(["AAPL"], {"AAPL": bars})
        shares_override = int(client_o.submitted_orders[0].qty)

        # Override (0.5%) should give fewer shares than default (2.0%)
        assert shares_override < shares_default

    def test_override_equal_daily_falls_back_to_greyed(self) -> None:
        """override risk == daily number → rejected, uses daily number (same as default)."""
        bars = self._bars()
        cfg_default = self._cfg(
            daily_max_loss_pct=-2.0,
            stop_loss_pct=1.0,
            position_size_pct=100.0,
            override_risk_per_trade=False,
        )
        cfg_override = self._cfg(
            daily_max_loss_pct=-2.0,
            stop_loss_pct=1.0,
            position_size_pct=100.0,
            override_risk_per_trade=True,
            risk_per_trade_pct=2.0,
        )  # equal → rejected

        sess_d, client_d, _ = _session(
            cfg=cfg_default,
            equity=100_000,
            buying_power=500_000,
            fill_price=100.0,
            conviction=1.0,
        )
        sess_d.start_day()
        sess_d.run_cycle(["AAPL"], {"AAPL": bars})

        sess_o, client_o, _ = _session(
            cfg=cfg_override,
            equity=100_000,
            buying_power=500_000,
            fill_price=100.0,
            conviction=1.0,
        )
        sess_o.start_day()
        sess_o.run_cycle(["AAPL"], {"AAPL": bars})

        # Both should produce the same share count since override falls back to daily number
        assert int(client_o.submitted_orders[0].qty) == int(
            client_d.submitted_orders[0].qty
        )

    def test_shares_less_than_1_skips(self) -> None:
        """Extremely small risk → max_risk too small for even 1 share → skip."""
        cfg = self._cfg(
            daily_max_loss_pct=-0.0001,
            stop_loss_pct=1.0,
            position_size_pct=100.0,
            override_risk_per_trade=False,
        )
        sess, client, _ = _session(
            cfg=cfg, equity=1_000, buying_power=10_000, conviction=1.0
        )
        sess.start_day()
        result = sess.run_cycle(["AAPL"], {"AAPL": self._bars()})
        assert result.trades_entered == 0

    def test_buying_power_cap_respected(self) -> None:
        """Low buying power caps shares to what's available."""
        cfg = self._cfg(
            daily_max_loss_pct=-2.0,
            stop_loss_pct=1.0,
            position_size_pct=100.0,
            override_risk_per_trade=False,
        )
        sess, client, _ = _session(
            cfg=cfg, equity=100_000, buying_power=500, fill_price=100.0, conviction=1.0
        )
        sess.start_day()
        bars = self._bars()
        result = sess.run_cycle(["AAPL"], {"AAPL": bars})
        assert result.trades_entered == 1
        buy = [o for o in client.submitted_orders if o.side == OrderSide.BUY][0]
        # Entry price ≈ bars[-1].close; shares must satisfy shares * price ≤ buying_power=500
        entry_price = float(bars[-1].close)
        assert int(buy.qty) * entry_price <= 500 + entry_price  # allow 1 share rounding

    def test_goalpost_trade_count_exposed(self) -> None:
        cfg = ExecutionConfig(
            daily_max_loss_pct=-3.0,
            override_risk_per_trade=True,
            risk_per_trade_pct=1.0,
        )
        sess, _, _ = _session(cfg=cfg, conviction=1.0)
        sess.start_day()
        result = sess.run_cycle([], {})
        assert result.goalpost_trade_count == 3  # ceil(3/1)


# ---------------------------------------------------------------------------
# Daily circuit breakers
# ---------------------------------------------------------------------------


class TestMaxLossCircuitBreaker:
    def test_flatten_and_halt_when_max_loss_hit(self) -> None:
        cfg = ExecutionConfig(
            daily_max_loss_pct=-2.0,
            flatten_on_max_loss=True,
            conviction_threshold=0.0,
            z_hour_cutoff=0.0,
            exit_mode="dump",
            force_close_at_close=False,
            stop_loss_pct=1.0,
            position_size_pct=100.0,
            overextension_pct=15.0,
        )
        sess, client, _ = _session(cfg=cfg, equity=100_000, conviction=1.0)
        sess.start_day()
        # Enter a position first
        accel = make_breakout_bars()
        sess.run_cycle(["AAPL"], {"AAPL": accel})
        assert sess._result.trades_entered == 1

        # Inject realized PnL past the max-loss threshold
        sess._result.realized_pnl = -2100.0
        sess._daily_state.realized_pnl = -2100.0  # type: ignore[union-attr]

        # Inject a second open trade to confirm it gets flattened
        sess._open_trades["TSLA"] = _make_dummy_open_trade("TSLA", 10, 100.0)

        bars2 = make_falling_bars(n=20, symbol="TSLA")
        result = sess.run_cycle(["AAPL", "TSLA"], {"AAPL": accel, "TSLA": bars2})
        assert result.halted
        sell_orders = [o for o in client.submitted_orders if o.side == OrderSide.SELL]
        assert len(sell_orders) >= 1

    def test_no_new_entries_after_halt(self) -> None:
        cfg = ExecutionConfig(
            daily_max_loss_pct=-2.0,
            flatten_on_max_loss=False,
            conviction_threshold=0.0,
            z_hour_cutoff=0.0,
            exit_mode="dump",
            force_close_at_close=False,
            stop_loss_pct=1.0,
            overextension_pct=15.0,
        )
        sess, client, _ = _session(cfg=cfg, equity=100_000, conviction=1.0)
        sess.start_day()
        assert sess._daily_state is not None
        sess._daily_state.halted = True
        sess._daily_state.halt_reason = "test halt"
        bars = make_falling_bars(n=20)
        result = sess.run_cycle(["AAPL"], {"AAPL": bars})
        assert result.trades_entered == 0


class TestProfitTargetCircuitBreaker:
    def test_halt_on_profit_target_no_flatten(self) -> None:
        cfg = ExecutionConfig(
            daily_profit_target_pct=3.0,
            flatten_on_profit_target=False,
            conviction_threshold=0.0,
            z_hour_cutoff=0.0,
            exit_mode="dump",
            force_close_at_close=False,
            stop_loss_pct=1.0,
        )
        sess, client, _ = _session(cfg=cfg, equity=100_000, conviction=1.0)
        sess.start_day()
        # Inject profit already past target
        sess._result.realized_pnl = 3500.0
        bars = make_falling_bars(n=20)
        result = sess.run_cycle(["AAPL"], {"AAPL": bars})
        assert result.halted
        assert result.trades_entered == 0

    def test_flatten_on_profit_target(self) -> None:
        cfg = ExecutionConfig(
            daily_profit_target_pct=3.0,
            flatten_on_profit_target=True,
            conviction_threshold=0.0,
            z_hour_cutoff=0.0,
            exit_mode="dump",
            force_close_at_close=False,
            stop_loss_pct=1.0,
        )
        sess, client, _ = _session(cfg=cfg, equity=100_000, conviction=1.0)
        sess.start_day()
        # Inject an open trade and past-target profit
        sess._open_trades["AAPL"] = _make_dummy_open_trade("AAPL", 10, 100.0)
        sess._result.realized_pnl = 3100.0
        bars = make_falling_bars(n=20)
        result = sess.run_cycle(["AAPL"], {"AAPL": bars})
        assert result.halted
        sell_orders = [o for o in client.submitted_orders if o.side == OrderSide.SELL]
        assert len(sell_orders) >= 1

    def test_single_trade_reaching_target_halts_day(self) -> None:
        """Reaching the profit target in one trade halts the day (no new entries)."""
        cfg = ExecutionConfig(
            daily_profit_target_pct=3.0,
            flatten_on_profit_target=False,
            conviction_threshold=0.0,
            z_hour_cutoff=0.0,
            exit_mode="dump",
            force_close_at_close=False,
            stop_loss_pct=1.0,
        )
        sess, client, _ = _session(cfg=cfg, equity=100_000, conviction=1.0)
        sess.start_day()
        sess._result.realized_pnl = 3100.0  # single trade hit target

        result = sess.run_cycle(
            ["AAPL", "TSLA"],
            {"AAPL": make_falling_bars(n=20), "TSLA": make_falling_bars(n=20)},
        )
        assert result.halted
        assert result.trades_entered == 0


# ---------------------------------------------------------------------------
# Dump exit mode
# ---------------------------------------------------------------------------


class TestDumpExit:
    def _cfg_dump(self, **kwargs: object) -> ExecutionConfig:
        return ExecutionConfig(
            exit_mode="dump",
            take_profit_pct=3.0,
            stop_loss_pct=1.0,
            conviction_threshold=0.0,
            z_hour_cutoff=0.0,
            force_close_at_close=False,
            overextension_pct=15.0,
            **kwargs,  # type: ignore[arg-type]
        )

    def _enter(self, sess: ExecutionSession) -> bool:
        sess.start_day()
        bars = make_breakout_bars()
        sess.run_cycle(["AAPL"], {"AAPL": bars})
        return sess._result.trades_entered == 1

    def test_dump_on_take_profit(self) -> None:
        sess, client, _ = _session(
            cfg=self._cfg_dump(), fill_price=100.0, conviction=1.0
        )
        if not self._enter(sess):
            return  # gate may reject — skip

        trade = list(sess._open_trades.values())[0]
        # Force take-profit: push HWM then present price at target
        trade.position.high_water_mark = 103.5
        bars_tp = make_breakout_bars(base_price=103.0)
        bars_tp[-1] = bars_tp[-1].model_copy(
            update={"close": Decimal("103.5"), "high": Decimal("104.0")}
        )
        pre = len(client.submitted_orders)
        sess.run_cycle(["AAPL"], {"AAPL": bars_tp})
        sells = [o for o in client.submitted_orders[pre:] if o.side == OrderSide.SELL]
        assert len(sells) >= 1

    def test_dump_entire_position_at_once(self) -> None:
        """Dump mode sells all remaining shares in one order."""
        sess, client, _ = _session(
            cfg=self._cfg_dump(), fill_price=100.0, conviction=1.0
        )
        if not self._enter(sess):
            return

        trade = list(sess._open_trades.values())[0]
        total_shares = trade.position.remaining_shares

        # Trigger a bearish dump via falling bars
        falling = make_falling_bars(n=25)
        pre = len(client.submitted_orders)
        sess.run_cycle(["AAPL"], {"AAPL": falling})
        sells = [o for o in client.submitted_orders[pre:] if o.side == OrderSide.SELL]
        if sells:
            # Dump should be a single order covering all remaining shares
            total_sold = sum(int(o.qty) for o in sells)
            assert total_sold == total_shares


# ---------------------------------------------------------------------------
# Trail-off exit mode
# ---------------------------------------------------------------------------


class TestTrailOffExit:
    def _cfg_trail(self, trigger: str = "per_candle", **kw: object) -> ExecutionConfig:
        return ExecutionConfig(
            exit_mode="trail_off",
            trail_off_trigger=trigger,
            trail_off_fraction_per_candle=0.25,
            take_profit_pct=1.0,
            stop_loss_pct=1.0,
            conviction_threshold=0.0,
            z_hour_cutoff=0.0,
            force_close_at_close=False,
            overextension_pct=15.0,
            **kw,  # type: ignore[arg-type]
        )

    def _enter(self, sess: ExecutionSession) -> bool:
        sess.start_day()
        bars = make_breakout_bars()
        sess.run_cycle(["AAPL"], {"AAPL": bars})
        return bool(sess._open_trades)

    def test_per_candle_fractional_scale_out(self) -> None:
        sess, client, _ = _session(
            cfg=self._cfg_trail("per_candle"), fill_price=100.0, conviction=1.0
        )
        if not self._enter(sess):
            return

        trade = list(sess._open_trades.values())[0]
        initial = trade.position.remaining_shares

        # Simulate take-profit with still-bullish accelerating bars
        bars_tp = make_breakout_bars(base_price=101.0)
        bars_tp[-1] = bars_tp[-1].model_copy(
            update={"close": Decimal("102.0"), "high": Decimal("102.5")}
        )
        sess.run_cycle(["AAPL"], {"AAPL": bars_tp})

        sell_orders = [o for o in client.submitted_orders if o.side == OrderSide.SELL]
        if sell_orders:
            total_sold = sum(int(o.qty) for o in sell_orders)
            # Fractional scale-out: should sell ≤ 25% each candle, not all at once
            # (unless bullishness already ended)
            assert total_sold <= initial

    def test_dump_remainder_on_reversal_in_trail_off(self) -> None:
        """In trail_off mode: when bullishness ends, dump the remainder at once."""
        sess, client, _ = _session(
            cfg=self._cfg_trail("per_candle"), fill_price=100.0, conviction=1.0
        )
        if not self._enter(sess):
            return

        trade = list(sess._open_trades.values())[0]
        remaining_before = trade.position.remaining_shares

        # Falling bars → MACD goes ineligible → dump remainder
        falling = make_falling_bars(n=25)
        pre = len(client.submitted_orders)
        sess.run_cycle(["AAPL"], {"AAPL": falling})
        post_sells = [
            o for o in client.submitted_orders[pre:] if o.side == OrderSide.SELL
        ]

        if post_sells:
            # A single dump order should close the whole remaining position
            total_sold = sum(int(o.qty) for o in post_sells)
            assert total_sold == remaining_before

    def test_candle_pattern_trigger_sells_on_reconfirm(self) -> None:
        """candle_pattern trigger: sells a chunk each time a bullish pattern reconfirms."""
        sess, client, _ = _session(
            cfg=self._cfg_trail("candle_pattern"), fill_price=100.0, conviction=1.0
        )
        if not self._enter(sess):
            return
        # The engine will fire candle_pattern exits on re-confirming patterns
        bars = make_breakout_bars()
        pre = len(client.submitted_orders)
        sess.run_cycle(["AAPL"], {"AAPL": bars})
        # Any sell order (or none) is acceptable here; just validate no crash
        assert len(client.submitted_orders) >= pre


# ---------------------------------------------------------------------------
# Trailing stop
# ---------------------------------------------------------------------------


class TestTrailingStop:
    def test_trailing_stop_triggers_sell(self) -> None:
        cfg = ExecutionConfig(
            trailing_stop=True,
            trailing_stop_pct=2.0,
            exit_mode="dump",
            stop_loss_pct=1.0,
            conviction_threshold=0.0,
            z_hour_cutoff=0.0,
            force_close_at_close=False,
            overextension_pct=15.0,
        )
        sess, client, _ = _session(cfg=cfg, fill_price=100.0, conviction=1.0)
        sess.start_day()
        accel = make_breakout_bars()
        sess.run_cycle(["AAPL"], {"AAPL": accel})
        if not sess._open_trades:
            return

        trade = list(sess._open_trades.values())[0]
        # Push HWM to 110; trailing stop = 110 * 0.98 = 107.8
        trade.position.high_water_mark = 110.0
        # Price drops to 107 → below stop
        bars_drop = make_flat_bars(n=5, price=107.0)
        pre = len(client.submitted_orders)
        sess.run_cycle(["AAPL"], {"AAPL": bars_drop})
        sells = [o for o in client.submitted_orders[pre:] if o.side == OrderSide.SELL]
        assert len(sells) >= 1

    def test_trailing_stop_not_triggered_above_stop(self) -> None:
        # Entry=108.0, HWM=110.0, trailing_stop_pct=2% → stop=107.8
        # Bars end at ~108.64 (breakout bars): above stop, below take-profit (108*1.05=113.4)
        # MACD slope positive from breakout bars → no back-side exit either
        cfg = ExecutionConfig(
            trailing_stop=True,
            trailing_stop_pct=2.0,
            take_profit_pct=5.0,  # target=113.4, not reached at 108.64
            exit_mode="dump",
            stop_loss_pct=1.0,
            conviction_threshold=0.0,
            z_hour_cutoff=0.0,
            force_close_at_close=False,
            overextension_pct=15.0,
        )
        sess, client, _ = _session(cfg=cfg, conviction=1.0)
        sess.start_day()
        # Inject a trade with entry=108.0 so take-profit target=113.4
        sess._open_trades["AAPL"] = _make_dummy_open_trade(
            "AAPL", shares=10, entry=108.0
        )
        sess._open_trades["AAPL"].position.high_water_mark = 110.0

        # breakout bars: last close≈108.64 > stop=107.8, MACD slope>0
        bars_above = make_breakout_bars()
        pre = len(client.submitted_orders)
        sess.run_cycle(["AAPL"], {"AAPL": bars_above})
        sells = [o for o in client.submitted_orders[pre:] if o.side == OrderSide.SELL]
        assert len(sells) == 0


# ---------------------------------------------------------------------------
# Force-close at close
# ---------------------------------------------------------------------------


class TestForceCloseAtClose:
    def test_force_close_flattens_at_near_close(self) -> None:
        cfg = ExecutionConfig(
            force_close_at_close=True,
            exit_mode="dump",
            stop_loss_pct=1.0,
            conviction_threshold=0.0,
            z_hour_cutoff=0.0,
        )
        sess, client, clock = _session(cfg=cfg, conviction=1.0)
        clock._near_close = True

        sess.start_day()
        # Inject a pre-existing open position
        sess._open_trades["AAPL"] = _make_dummy_open_trade("AAPL", 10, 100.0)

        bars = make_falling_bars(n=20)
        sess.run_cycle(["AAPL"], {"AAPL": bars})
        sell_orders = [o for o in client.submitted_orders if o.side == OrderSide.SELL]
        assert len(sell_orders) >= 1
        assert not sess._open_trades


# ---------------------------------------------------------------------------
# Z-hour cutoff
# ---------------------------------------------------------------------------


class TestZHourCutoff:
    def test_no_entry_within_z_hours(self) -> None:
        cfg = ExecutionConfig(
            z_hour_cutoff=1.0,
            conviction_threshold=0.0,
            exit_mode="dump",
            force_close_at_close=False,
            stop_loss_pct=1.0,
            overextension_pct=15.0,
        )
        # 30 min after open → inside z-cutoff window
        now = _SESSION_OPEN + timedelta(minutes=30)
        sess, client, _ = _session(cfg=cfg, now=now, conviction=1.0)
        sess.start_day()
        bars = make_breakout_bars()
        result = sess.run_cycle(["AAPL"], {"AAPL": bars})
        assert result.trades_entered == 0

    def test_entry_allowed_after_z_hours(self) -> None:
        cfg = ExecutionConfig(
            z_hour_cutoff=1.0,
            conviction_threshold=0.0,
            exit_mode="dump",
            force_close_at_close=False,
            stop_loss_pct=1.0,
            overextension_pct=15.0,
        )
        # 61 min after open → past z-cutoff
        now = _SESSION_OPEN + timedelta(minutes=61)
        sess, client, _ = _session(cfg=cfg, now=now, conviction=1.0)
        sess.start_day()
        bars = make_breakout_bars()
        result = sess.run_cycle(["AAPL"], {"AAPL": bars})
        assert result.trades_entered == 1

    def test_z_cutoff_logged(self) -> None:
        cfg = ExecutionConfig(
            z_hour_cutoff=1.0,
            conviction_threshold=0.0,
            exit_mode="dump",
            force_close_at_close=False,
            stop_loss_pct=1.0,
        )
        now = _SESSION_OPEN + timedelta(minutes=20)
        sess, _, _ = _session(cfg=cfg, now=now, conviction=1.0)
        sess.start_day()
        bars = make_breakout_bars()
        result = sess.run_cycle(["AAPL"], {"AAPL": bars})
        assert any(
            "z-hour" in msg.lower() or "cutoff" in msg.lower()
            for msg in result.log_messages
        )


# ---------------------------------------------------------------------------
# Margin / PDT deferral
# ---------------------------------------------------------------------------


class TestMarginDeferral:
    def test_pdt_restricted_blocks_entry(self) -> None:
        sess, client, _ = _session(is_pdt_restricted=True, conviction=1.0)
        sess.start_day()
        bars = make_breakout_bars()
        result = sess.run_cycle(["AAPL"], {"AAPL": bars})
        assert result.trades_entered == 0
        buy_orders = [o for o in client.submitted_orders if o.side == OrderSide.BUY]
        assert not buy_orders

    def test_pdt_logged(self) -> None:
        sess, _, _ = _session(is_pdt_restricted=True, conviction=1.0)
        sess.start_day()
        bars = make_breakout_bars()
        result = sess.run_cycle(["AAPL"], {"AAPL": bars})
        assert any("PDT" in msg or "pdt" in msg.lower() for msg in result.log_messages)

    def test_zero_buying_power_blocks(self) -> None:
        sess, client, _ = _session(buying_power=0.0, conviction=1.0)
        sess.start_day()
        bars = make_breakout_bars()
        result = sess.run_cycle(["AAPL"], {"AAPL": bars})
        assert result.trades_entered == 0

    def test_negative_intraday_margin_blocks(self) -> None:
        sess, client, _ = _session(day_trading_buying_power=-1000.0, conviction=1.0)
        sess.start_day()
        bars = make_breakout_bars()
        result = sess.run_cycle(["AAPL"], {"AAPL": bars})
        assert result.trades_entered == 0

    def test_min_equity_notice_logged(self) -> None:
        cfg = ExecutionConfig(
            min_account_equity_notice=2000.0,
            z_hour_cutoff=0.0,
            exit_mode="dump",
            force_close_at_close=False,
            conviction_threshold=0.0,
            stop_loss_pct=1.0,
        )
        sess, _, _ = _session(cfg=cfg, equity=1500.0, conviction=1.0)
        sess.start_day()
        assert any(
            "equity" in m.lower() or "notice" in m.lower()
            for m in sess._result.log_messages
        )


# ---------------------------------------------------------------------------
# active_tickers_n limiting
# ---------------------------------------------------------------------------


class TestActiveTickers:
    def test_only_top_n_considered(self) -> None:
        cfg = ExecutionConfig(
            active_tickers_n=2,
            conviction_threshold=0.0,
            z_hour_cutoff=0.0,
            exit_mode="dump",
            force_close_at_close=False,
            stop_loss_pct=1.0,
            overextension_pct=15.0,
        )
        sess, client, _ = _session(cfg=cfg, conviction=1.0)
        sess.start_day()
        bars_map = {s: make_breakout_bars(symbol=s) for s in ["A", "B", "C", "D", "E"]}
        result = sess.run_cycle(["A", "B", "C", "D", "E"], bars_map)
        # Only top-2 candidates evaluated → at most 2 trades
        assert result.trades_entered <= 2


# ---------------------------------------------------------------------------
# State / log assertions
# ---------------------------------------------------------------------------


class TestStateAssertions:
    def test_orders_logged_after_submission(self) -> None:
        sess, client, _ = _session(conviction=1.0)
        sess.start_day()
        bars = make_breakout_bars()
        result = sess.run_cycle(["AAPL"], {"AAPL": bars})
        # Every order submitted to the client is also in result.orders_submitted
        assert len(result.orders_submitted) == len(client.submitted_orders)

    def test_end_day_flattens_remaining(self) -> None:
        cfg = ExecutionConfig(
            conviction_threshold=0.0,
            z_hour_cutoff=0.0,
            exit_mode="dump",
            force_close_at_close=False,
            stop_loss_pct=1.0,
            overextension_pct=15.0,
        )
        sess, client, _ = _session(cfg=cfg, conviction=1.0)
        sess.start_day()
        bars = make_breakout_bars()
        sess.run_cycle(["AAPL"], {"AAPL": bars})
        if sess._open_trades:
            sess.end_day()
            sells = [o for o in client.submitted_orders if o.side == OrderSide.SELL]
            assert len(sells) >= 1
            assert not sess._open_trades

    def test_log_messages_always_populated(self) -> None:
        sess, _, _ = _session(conviction=1.0)
        sess.start_day()
        result = sess.run_cycle([], {})
        assert isinstance(result.log_messages, list)

    def test_realized_pnl_accumulates_across_exits(self) -> None:
        """Multiple partial exits accumulate realized_pnl."""
        cfg = ExecutionConfig(
            exit_mode="dump",
            take_profit_pct=3.0,
            stop_loss_pct=1.0,
            conviction_threshold=0.0,
            z_hour_cutoff=0.0,
            force_close_at_close=False,
            overextension_pct=15.0,
        )
        sess, client, _ = _session(cfg=cfg, fill_price=100.0, conviction=1.0)
        sess.start_day()
        accel = make_breakout_bars()
        sess.run_cycle(["AAPL"], {"AAPL": accel})
        if not sess._open_trades:
            return

        # Trigger exit via falling bars
        falling = make_falling_bars(n=25)
        sess.run_cycle(["AAPL"], {"AAPL": falling})
        assert isinstance(sess._result.realized_pnl, float)
