"""Tests: labeling correctness for longs and shorts."""

from __future__ import annotations

import pytest

from bot.learning.labeling import label_from_pnl, trade_label_str


class TestLabelFromPnl:
    def test_positive_pnl_is_good(self):
        assert label_from_pnl(100.0) == 1

    def test_small_positive_pnl_is_good(self):
        assert label_from_pnl(0.01) == 1

    def test_negative_pnl_is_bad(self):
        assert label_from_pnl(-50.0) == 0

    def test_zero_pnl_is_bad(self):
        # Break-even is not a good trade
        assert label_from_pnl(0.0) == 0

    def test_large_loss_is_bad(self):
        assert label_from_pnl(-9999.99) == 0

    def test_long_trade_profit(self):
        # Long: bought at 10, sold at 12 → net +2 after fees
        entry, exit_p, qty, fees = 10.0, 12.0, 100, 1.5
        net_pnl = (exit_p - entry) * qty - fees
        assert label_from_pnl(net_pnl) == 1

    def test_long_trade_loss(self):
        # Long: bought at 10, sold at 9 → net loss
        entry, exit_p, qty, fees = 10.0, 9.0, 100, 0.5
        net_pnl = (exit_p - entry) * qty - fees
        assert label_from_pnl(net_pnl) == 0

    def test_short_trade_profit(self):
        # Short: shorted at 10, bought back at 8 → profit
        entry, exit_p, qty, fees = 10.0, 8.0, 100, 1.0
        net_pnl = (entry - exit_p) * qty - fees  # short P&L sign convention
        assert label_from_pnl(net_pnl) == 1

    def test_short_trade_loss(self):
        # Short: shorted at 10, bought back at 12 → loss
        entry, exit_p, qty, fees = 10.0, 12.0, 100, 0.5
        net_pnl = (entry - exit_p) * qty - fees
        assert label_from_pnl(net_pnl) == 0


class TestTradeLabelStr:
    def test_positive_returns_good(self):
        assert trade_label_str(50.0) == "good"

    def test_negative_returns_bad(self):
        assert trade_label_str(-10.0) == "bad"

    def test_zero_returns_bad(self):
        assert trade_label_str(0.0) == "bad"
