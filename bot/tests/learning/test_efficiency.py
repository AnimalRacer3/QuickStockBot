"""Tests: trades_to_goal computation + tuner lowers trades_to_goal on synthetic data."""

from __future__ import annotations

import math

import pytest

from bot.learning.efficiency import (
    DayTracker,
    EfficiencyTuner,
    TradeRecord,
    _trades_to_goal,
)


# ---------------------------------------------------------------------------
# _trades_to_goal helper
# ---------------------------------------------------------------------------


class TestTradesToGoal:
    def test_empty_list_returns_zero_unreached(self):
        ttg, reached = _trades_to_goal([], 2.0)
        assert ttg == 0
        assert reached is False

    def test_single_trade_reaches_target(self):
        ttg, reached = _trades_to_goal([3.0], 2.0)
        assert ttg == 1
        assert reached is True

    def test_single_trade_below_target(self):
        ttg, reached = _trades_to_goal([1.0], 2.0)
        assert ttg == 1
        assert reached is False

    def test_multiple_trades_reach_at_second(self):
        ttg, reached = _trades_to_goal([1.0, 1.5], 2.0)
        assert ttg == 2
        assert reached is True

    def test_multiple_trades_reach_exactly(self):
        ttg, reached = _trades_to_goal([1.0, 1.0], 2.0)
        assert ttg == 2
        assert reached is True

    def test_never_reaches_target(self):
        ttg, reached = _trades_to_goal([0.3, 0.4, 0.2], 2.0)
        assert ttg == 3
        assert reached is False

    def test_reaches_at_first_trade(self):
        ttg, reached = _trades_to_goal([5.0, 1.0, 1.0], 2.0)
        assert ttg == 1
        assert reached is True

    def test_losses_dont_prematurely_end(self):
        # -1.0, +2.0, +2.0 → cumsum at trade 2 = 1.0, trade 3 = 3.0
        ttg, reached = _trades_to_goal([-1.0, 2.0, 2.0], 2.0)
        assert ttg == 3
        assert reached is True

    def test_target_zero_any_trade_reaches(self):
        ttg, reached = _trades_to_goal([0.01], 0.0)
        assert ttg == 1
        assert reached is True


# ---------------------------------------------------------------------------
# DayTracker
# ---------------------------------------------------------------------------


class TestDayTracker:
    def test_finish_day_goal_reached(self):
        tracker = DayTracker()
        tracker.start_day("2024-01-02")
        tracker.record_trade(1.5, 0.8)
        tracker.record_trade(1.0, 0.7)  # cumsum = 2.5 ≥ 2.0
        record = tracker.finish_day(daily_profit_target_pct=2.0)

        assert record.date == "2024-01-02"
        assert record.goal_reached is True
        assert record.trades_to_goal == 2
        assert record.daily_pnl_pct == pytest.approx(2.5)

    def test_finish_day_goal_not_reached(self):
        tracker = DayTracker()
        tracker.start_day("2024-01-03")
        tracker.record_trade(0.5, 0.4)
        tracker.record_trade(0.3, 0.3)
        record = tracker.finish_day(daily_profit_target_pct=2.0)

        assert record.goal_reached is False
        assert record.trades_to_goal == 2
        assert record.daily_pnl_pct == pytest.approx(0.8)

    def test_finish_day_single_large_trade(self):
        tracker = DayTracker()
        tracker.start_day("2024-01-04")
        tracker.record_trade(5.0, 0.95)  # exceeds target immediately
        record = tracker.finish_day(daily_profit_target_pct=2.0)

        assert record.goal_reached is True
        assert record.trades_to_goal == 1

    def test_finish_day_no_trades(self):
        tracker = DayTracker()
        tracker.start_day("2024-01-05")
        record = tracker.finish_day(daily_profit_target_pct=2.0)
        assert record.trades_to_goal == 0
        assert record.goal_reached is False
        assert record.daily_pnl_pct == pytest.approx(0.0)

    def test_finish_day_resets_tracker(self):
        tracker = DayTracker()
        tracker.start_day("2024-01-02")
        tracker.record_trade(3.0, 0.9)
        tracker.finish_day(2.0)

        # New day should be empty
        tracker.start_day("2024-01-03")
        record = tracker.finish_day(2.0)
        assert record.trades_to_goal == 0
        assert record.daily_pnl_pct == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# EfficiencyTuner — goal_post
# ---------------------------------------------------------------------------


class TestGoalPost:
    def test_standard_case(self):
        tuner = EfficiencyTuner()
        # max_loss=2%, risk=0.5% → 4 trades
        assert tuner.compute_goal_post(-2.0, 0.5) == 4

    def test_fractional_result_rounds_up(self):
        tuner = EfficiencyTuner()
        # max_loss=3%, risk=2% → 1.5 → ceil = 2
        assert tuner.compute_goal_post(-3.0, 2.0) == 2

    def test_already_integer(self):
        tuner = EfficiencyTuner()
        assert tuner.compute_goal_post(-4.0, 2.0) == 2

    def test_max_loss_as_positive_abs(self):
        tuner = EfficiencyTuner()
        # abs() handles both -2.0 and 2.0 the same
        assert tuner.compute_goal_post(2.0, 0.5) == 4

    def test_zero_risk_raises(self):
        tuner = EfficiencyTuner()
        with pytest.raises(ValueError):
            tuner.compute_goal_post(-2.0, 0.0)


# ---------------------------------------------------------------------------
# EfficiencyTuner — tune / simulate_threshold
# ---------------------------------------------------------------------------

def _make_day_records(n_days: int = 10) -> list[TradeRecord]:
    """Synthetic dataset: each day has 4 low-conviction trades (+0.4% each)
    and 1 high-conviction trade (+2.5%).

    Ordered within each day as [low, low, low, low, high].

    At threshold=0.0: need 5 low-conv trades to reach 4×0.4=1.6, no that's
    only 1.6. Let's use 5 low-conv at 0.4 each = 2.0 exactly.

    Actually let's use 5 low-conv at 0.5% each. Then:
    - threshold=0.0: cumsum at 4th = 2.0 ≥ 2.0 → trades_to_goal=4
    - threshold=0.8: only high-conv → 1 trade at 2.5% → trades_to_goal=1
    """
    records: list[TradeRecord] = []
    for day in range(n_days):
        date = f"2024-01-{day + 1:02d}"
        # 4 low-conviction trades at +0.5% each
        for _ in range(4):
            records.append(TradeRecord(date=date, net_pnl_pct=0.5, conviction_score=0.3))
        # 1 high-conviction trade at +2.5%
        records.append(TradeRecord(date=date, net_pnl_pct=2.5, conviction_score=0.9))
    return records


class TestEfficiencyTuner:
    def test_simulate_threshold_all_trades(self):
        records = _make_day_records(n_days=5)
        tuner = EfficiencyTuner()
        result = tuner.simulate_threshold(records, threshold=0.0, daily_profit_target_pct=2.0)

        # 4 low-conv at 0.5% = 2.0% reached at 4th trade
        assert result.avg_trades_to_goal == pytest.approx(4.0)
        assert result.hit_rate == pytest.approx(1.0)
        assert result.days_with_trades == 5

    def test_simulate_threshold_high_conviction_only(self):
        records = _make_day_records(n_days=5)
        tuner = EfficiencyTuner()
        result = tuner.simulate_threshold(records, threshold=0.8, daily_profit_target_pct=2.0)

        # Only the high-conv trade at +2.5% → target reached at trade 1
        assert result.avg_trades_to_goal == pytest.approx(1.0)
        assert result.hit_rate == pytest.approx(1.0)

    def test_tuner_recommends_high_threshold(self):
        records = _make_day_records(n_days=10)
        tuner = EfficiencyTuner()
        report = tuner.tune(
            trade_records=records,
            candidate_thresholds=[0.0, 0.3, 0.5, 0.8, 0.95],
            daily_profit_target_pct=2.0,
            min_hit_rate=0.8,
        )
        # Any threshold >= 0.5 filters out low-conv trades (score=0.3) and
        # picks only the high-conv trade (score=0.9) → trades_to_goal=1
        assert report.avg_trades_to_goal == pytest.approx(1.0)
        # The recommended threshold must be one that excludes the low-conv trades
        assert report.recommended_threshold >= 0.4

    def test_tuner_lowers_trades_to_goal_vs_no_threshold(self):
        records = _make_day_records(n_days=10)
        tuner = EfficiencyTuner()

        base = tuner.simulate_threshold(records, threshold=0.0, daily_profit_target_pct=2.0)
        report = tuner.tune(
            records,
            candidate_thresholds=[0.0, 0.5, 0.8, 0.95],
            daily_profit_target_pct=2.0,
            min_hit_rate=0.8,
        )
        assert report.avg_trades_to_goal <= base.avg_trades_to_goal

    def test_tuner_goal_post_in_report(self):
        records = _make_day_records(n_days=5)
        tuner = EfficiencyTuner()
        report = tuner.tune(
            records,
            candidate_thresholds=[0.5, 0.8],
            daily_profit_target_pct=2.0,
            daily_max_loss_pct=-2.0,
            risk_per_trade_pct=0.5,
        )
        assert report.goal_post == 4  # ceil(2.0 / 0.5)

    def test_tuner_threshold_results_contains_all_candidates(self):
        records = _make_day_records(n_days=5)
        tuner = EfficiencyTuner()
        thresholds = [0.3, 0.6, 0.9]
        report = tuner.tune(records, thresholds, daily_profit_target_pct=2.0)
        result_thresholds = [r.threshold for r in report.threshold_results]
        assert result_thresholds == thresholds

    def test_simulate_threshold_above_all_convictions_no_trades(self):
        records = _make_day_records(n_days=3)
        tuner = EfficiencyTuner()
        # threshold > 0.9 (max conviction in records) → no trades
        result = tuner.simulate_threshold(records, threshold=0.99, daily_profit_target_pct=2.0)
        assert result.days_with_trades == 0
        assert result.hit_rate == pytest.approx(0.0)
        assert math.isinf(result.avg_trades_to_goal)

    def test_tuner_falls_back_when_no_threshold_meets_min_hit_rate(self):
        # All trades are small P&L — no threshold can reach the target
        records = [
            TradeRecord(date="2024-01-01", net_pnl_pct=0.1, conviction_score=0.9),
            TradeRecord(date="2024-01-02", net_pnl_pct=0.1, conviction_score=0.9),
        ]
        tuner = EfficiencyTuner()
        # daily_profit_target_pct is very high → no day reaches it
        report = tuner.tune(
            records,
            candidate_thresholds=[0.5, 0.8, 0.95],
            daily_profit_target_pct=100.0,
            min_hit_rate=0.9,
        )
        # Falls back gracefully — report is produced
        assert isinstance(report.recommended_threshold, float)
