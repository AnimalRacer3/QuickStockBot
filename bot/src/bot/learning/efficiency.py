"""Trade-efficiency incentive: tracks trades_to_goal and tunes conviction threshold."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional


@dataclass
class DailyEfficiencyRecord:
    """Summary of a single trading day's efficiency."""

    date: str          # YYYY-MM-DD
    trades_to_goal: int
    goal_reached: bool
    daily_pnl_pct: float


@dataclass
class TradeRecord:
    """A single completed round-trip for efficiency analysis."""

    date: str                # YYYY-MM-DD
    net_pnl_pct: float       # net P&L as % of account/portfolio
    conviction_score: float  # ML score at the time of entry (0..1)


@dataclass
class ThresholdResult:
    threshold: float
    avg_trades_to_goal: float
    hit_rate: float        # fraction of days where daily_profit_target_pct was reached
    days_with_trades: int


@dataclass
class EfficiencyReport:
    recommended_threshold: float
    avg_trades_to_goal: float
    hit_rate: float
    goal_post: int
    threshold_results: list[ThresholdResult]


# ---------------------------------------------------------------------------
# DayTracker
# ---------------------------------------------------------------------------


class DayTracker:
    """Tracks the current day's round-trips and computes trades_to_goal.

    Each completed round-trip should be recorded via ``record_trade``.
    Call ``finish_day`` at market close to produce the DailyEfficiencyRecord.
    """

    def __init__(self) -> None:
        self._trades: list[tuple[float, float]] = []  # (net_pnl_pct, conviction_score)
        self._current_date: Optional[str] = None

    def start_day(self, date: str) -> None:
        self._current_date = date
        self._trades = []

    def record_trade(self, net_pnl_pct: float, conviction_score: float) -> None:
        self._trades.append((net_pnl_pct, conviction_score))

    def finish_day(self, daily_profit_target_pct: float) -> DailyEfficiencyRecord:
        date = self._current_date or "unknown"
        pnls = [t[0] for t in self._trades]
        ttg, reached = _trades_to_goal(pnls, daily_profit_target_pct)
        record = DailyEfficiencyRecord(
            date=date,
            trades_to_goal=ttg,
            goal_reached=reached,
            daily_pnl_pct=sum(pnls),
        )
        self._trades = []
        self._current_date = None
        return record


# ---------------------------------------------------------------------------
# EfficiencyTuner
# ---------------------------------------------------------------------------


class EfficiencyTuner:
    """Recommends the conviction_threshold that minimises trades_to_goal.

    The *goal-post* formula encodes "reach the daily profit target in as few
    trades as possible":

        goal_post = ceil(|daily_max_loss_pct| / risk_per_trade_pct)

    e.g. max_loss=2%, risk_per_trade=0.5% → goal_post=4 (4 losing trades
    would hit the stop).  The ideal is 1 high-conviction trade to goal.
    """

    def compute_goal_post(
        self, daily_max_loss_pct: float, risk_per_trade_pct: float
    ) -> int:
        if risk_per_trade_pct <= 0:
            raise ValueError("risk_per_trade_pct must be > 0")
        return math.ceil(abs(daily_max_loss_pct) / risk_per_trade_pct)

    def simulate_threshold(
        self,
        trade_records: list[TradeRecord],
        threshold: float,
        daily_profit_target_pct: float,
    ) -> ThresholdResult:
        """Evaluate a single threshold over the historical trade records."""
        by_date: dict[str, list[float]] = {}
        for tr in trade_records:
            if tr.conviction_score >= threshold:
                by_date.setdefault(tr.date, []).append(tr.net_pnl_pct)

        days_with_trades = len(by_date)
        if days_with_trades == 0:
            return ThresholdResult(
                threshold=threshold,
                avg_trades_to_goal=float("inf"),
                hit_rate=0.0,
                days_with_trades=0,
            )

        total_ttg = 0
        goal_count = 0
        for pnls in by_date.values():
            ttg, reached = _trades_to_goal(pnls, daily_profit_target_pct)
            total_ttg += ttg
            if reached:
                goal_count += 1

        return ThresholdResult(
            threshold=threshold,
            avg_trades_to_goal=total_ttg / days_with_trades,
            hit_rate=goal_count / days_with_trades,
            days_with_trades=days_with_trades,
        )

    def tune(
        self,
        trade_records: list[TradeRecord],
        candidate_thresholds: list[float],
        daily_profit_target_pct: float,
        *,
        daily_max_loss_pct: float = -2.0,
        risk_per_trade_pct: float = 0.5,
        min_hit_rate: float = 0.5,
    ) -> EfficiencyReport:
        """Find the threshold minimising avg_trades_to_goal subject to min_hit_rate.

        If no threshold meets min_hit_rate, the one with the highest hit_rate is
        returned (the constraint is relaxed rather than returning no recommendation).
        """
        goal_post = self.compute_goal_post(daily_max_loss_pct, risk_per_trade_pct)
        results: list[ThresholdResult] = [
            self.simulate_threshold(trade_records, t, daily_profit_target_pct)
            for t in candidate_thresholds
        ]

        # Primary: meets min_hit_rate, minimise avg_trades_to_goal
        eligible = [r for r in results if r.hit_rate >= min_hit_rate and r.days_with_trades > 0]
        if eligible:
            best = min(eligible, key=lambda r: r.avg_trades_to_goal)
        else:
            # Relax: pick highest hit_rate among thresholds with any trades
            with_trades = [r for r in results if r.days_with_trades > 0]
            if not with_trades:
                # No trades survive any threshold — return lowest threshold
                best = results[0] if results else ThresholdResult(
                    threshold=candidate_thresholds[0] if candidate_thresholds else 0.5,
                    avg_trades_to_goal=float("inf"),
                    hit_rate=0.0,
                    days_with_trades=0,
                )
            else:
                best = max(with_trades, key=lambda r: r.hit_rate)

        return EfficiencyReport(
            recommended_threshold=best.threshold,
            avg_trades_to_goal=best.avg_trades_to_goal,
            hit_rate=best.hit_rate,
            goal_post=goal_post,
            threshold_results=results,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _trades_to_goal(pnls: list[float], target: float) -> tuple[int, bool]:
    """Return (count, reached): trades taken until cumulative P&L >= target."""
    if not pnls:
        return 0, False
    cumsum = 0.0
    for i, pnl in enumerate(pnls, 1):
        cumsum += pnl
        if cumsum >= target:
            return i, True
    return len(pnls), False
