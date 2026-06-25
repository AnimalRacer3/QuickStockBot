"""Tests: prior-profit stats aggregate correctly (multi-trade, longs + shorts)."""

from __future__ import annotations

import pytest

from bot.learning.prior_profit import PriorProfitTracker, TickerProfitStats


class TestTickerProfitStats:
    def test_win_rate_zero_when_no_trades(self):
        stats = TickerProfitStats(symbol="AAPL")
        assert stats.win_rate == pytest.approx(0.0)

    def test_win_rate_all_wins(self):
        stats = TickerProfitStats(symbol="AAPL", trade_count=4, win_count=4)
        assert stats.win_rate == pytest.approx(1.0)

    def test_win_rate_half(self):
        stats = TickerProfitStats(symbol="AAPL", trade_count=10, win_count=5)
        assert stats.win_rate == pytest.approx(0.5)

    def test_win_rate_zero_wins(self):
        stats = TickerProfitStats(symbol="AAPL", trade_count=3, win_count=0)
        assert stats.win_rate == pytest.approx(0.0)


class TestPriorProfitTracker:
    def test_initial_state_empty(self):
        tracker = PriorProfitTracker()
        assert tracker.get_stats("AAPL") is None
        assert tracker.all_stats() == []

    def test_record_first_trade_creates_entry(self):
        tracker = PriorProfitTracker()
        stats = tracker.record_trade("AAPL", net_pnl=100.0)
        assert stats.symbol == "AAPL"
        assert stats.cumulative_pnl == pytest.approx(100.0)
        assert stats.trade_count == 1
        assert stats.win_count == 1

    def test_record_losing_trade(self):
        tracker = PriorProfitTracker()
        stats = tracker.record_trade("TSLA", net_pnl=-50.0)
        assert stats.cumulative_pnl == pytest.approx(-50.0)
        assert stats.trade_count == 1
        assert stats.win_count == 0

    def test_multiple_trades_same_symbol_accumulate(self):
        tracker = PriorProfitTracker()
        tracker.record_trade("AAPL", net_pnl=200.0)
        tracker.record_trade("AAPL", net_pnl=-75.0)
        tracker.record_trade("AAPL", net_pnl=300.0)

        stats = tracker.get_stats("AAPL")
        assert stats is not None
        assert stats.cumulative_pnl == pytest.approx(425.0)
        assert stats.trade_count == 3
        assert stats.win_count == 2
        assert stats.win_rate == pytest.approx(2 / 3)

    def test_multiple_symbols_tracked_independently(self):
        tracker = PriorProfitTracker()
        tracker.record_trade("AAPL", net_pnl=100.0)
        tracker.record_trade("TSLA", net_pnl=-40.0)
        tracker.record_trade("NVDA", net_pnl=250.0)

        aapl = tracker.get_stats("AAPL")
        tsla = tracker.get_stats("TSLA")
        nvda = tracker.get_stats("NVDA")
        assert aapl is not None
        assert tsla is not None
        assert nvda is not None
        assert aapl.cumulative_pnl == pytest.approx(100.0)
        assert tsla.cumulative_pnl == pytest.approx(-40.0)
        assert nvda.cumulative_pnl == pytest.approx(250.0)
        assert len(tracker.all_stats()) == 3

    def test_long_trade_profit(self):
        tracker = PriorProfitTracker()
        # Long: bought at 10, sold at 12, qty=100, fees=1
        net_pnl = (12.0 - 10.0) * 100 - 1.0
        tracker.record_trade("AAPL", net_pnl=net_pnl)
        stats = tracker.get_stats("AAPL")
        assert stats is not None
        assert stats.cumulative_pnl == pytest.approx(199.0)
        assert stats.win_count == 1

    def test_short_trade_profit(self):
        tracker = PriorProfitTracker()
        # Short: shorted at 10, covered at 8, qty=100, fees=1
        net_pnl = (10.0 - 8.0) * 100 - 1.0
        tracker.record_trade("TSLA", net_pnl=net_pnl)
        stats = tracker.get_stats("TSLA")
        assert stats is not None
        assert stats.cumulative_pnl == pytest.approx(199.0)
        assert stats.win_count == 1

    def test_short_trade_loss(self):
        tracker = PriorProfitTracker()
        # Short: shorted at 10, covered at 11, qty=50, fees=0.5
        net_pnl = (10.0 - 11.0) * 50 - 0.5
        tracker.record_trade("AMD", net_pnl=net_pnl)
        stats = tracker.get_stats("AMD")
        assert stats is not None
        assert stats.cumulative_pnl < 0
        assert stats.win_count == 0

    def test_zero_pnl_not_counted_as_win(self):
        tracker = PriorProfitTracker()
        tracker.record_trade("AAPL", net_pnl=0.0)
        stats = tracker.get_stats("AAPL")
        assert stats is not None
        assert stats.win_count == 0
        assert stats.trade_count == 1

    def test_prior_profit_lookup_returns_cumulative_pnl(self):
        tracker = PriorProfitTracker()
        tracker.record_trade("AAPL", net_pnl=500.0)
        tracker.record_trade("AAPL", net_pnl=300.0)

        lookup = tracker.as_prior_profit_lookup()
        assert lookup("AAPL") == pytest.approx(800.0)

    def test_prior_profit_lookup_returns_none_for_unknown(self):
        tracker = PriorProfitTracker()
        lookup = tracker.as_prior_profit_lookup()
        assert lookup("UNKNOWN") is None

    def test_prior_profit_lookup_negative_cumulative(self):
        tracker = PriorProfitTracker()
        tracker.record_trade("TSLA", net_pnl=-100.0)
        tracker.record_trade("TSLA", net_pnl=-50.0)

        lookup = tracker.as_prior_profit_lookup()
        assert lookup("TSLA") == pytest.approx(-150.0)

    def test_initial_stats_pre_loaded(self):
        initial = {
            "AAPL": TickerProfitStats(
                symbol="AAPL", cumulative_pnl=1000.0, trade_count=5, win_count=4
            )
        }
        tracker = PriorProfitTracker(initial_stats=initial)
        stats = tracker.get_stats("AAPL")
        assert stats is not None
        assert stats.cumulative_pnl == pytest.approx(1000.0)
        assert stats.win_rate == pytest.approx(0.8)

    def test_adding_to_pre_loaded_stats(self):
        initial = {
            "AAPL": TickerProfitStats(
                symbol="AAPL", cumulative_pnl=100.0, trade_count=2, win_count=2
            )
        }
        tracker = PriorProfitTracker(initial_stats=initial)
        tracker.record_trade("AAPL", net_pnl=-30.0)

        stats = tracker.get_stats("AAPL")
        assert stats is not None
        assert stats.cumulative_pnl == pytest.approx(70.0)
        assert stats.trade_count == 3
        assert stats.win_count == 2
