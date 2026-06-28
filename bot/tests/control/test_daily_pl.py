"""
Daily P/L color-coding logic tests.

Color rules:
  green  → ran AND net_pl > 0
  red    → ran AND net_pl < 0
  blue   → ran AND (net_pl == 0 OR trade_count == 0)
  omit   → day not in run_days
"""

from __future__ import annotations

import datetime

import pytest

from bot.control.connection import DbConn
from bot.control.db import get_daily_pl, mark_run_day
from tests.control.conftest import insert_order, insert_trade

# ─── Helpers ──────────────────────────────────────────────────────────────────


def _ts_for_date(date_str: str) -> int:
    d = datetime.date.fromisoformat(date_str)
    return int(
        datetime.datetime(
            d.year, d.month, d.day, 12, 0, 0, tzinfo=datetime.timezone.utc
        ).timestamp()
    )


def _add_trade_on(conn: sqlite3.Connection, date_str: str, net_pnl: float) -> None:
    oid = insert_order(conn)
    insert_trade(
        conn, entry_order_id=oid, net_pnl=net_pnl, closed_at=_ts_for_date(date_str)
    )


# ─── Tests ────────────────────────────────────────────────────────────────────


class TestDailyPLColors:
    def test_profit_day_is_green(self, db: DbConn) -> None:
        mark_run_day(db, "2024-03-01")
        _add_trade_on(db, "2024-03-01", net_pnl=200.0)
        days = get_daily_pl(db, "2024-03-01", "2024-03-01")
        assert len(days) == 1
        assert days[0]["color"] == "green"
        assert days[0]["net_pl"] == pytest.approx(200.0)

    def test_loss_day_is_red(self, db: DbConn) -> None:
        mark_run_day(db, "2024-03-02")
        _add_trade_on(db, "2024-03-02", net_pnl=-150.0)
        days = get_daily_pl(db, "2024-03-02", "2024-03-02")
        assert days[0]["color"] == "red"
        assert days[0]["net_pl"] == pytest.approx(-150.0)

    def test_flat_day_is_blue(self, db: DbConn) -> None:
        mark_run_day(db, "2024-03-03")
        _add_trade_on(db, "2024-03-03", net_pnl=0.0)
        days = get_daily_pl(db, "2024-03-03", "2024-03-03")
        assert days[0]["color"] == "blue"
        assert days[0]["net_pl"] == pytest.approx(0.0)
        assert days[0]["trade_count"] == 1

    def test_ran_but_no_trades_is_blue(self, db: DbConn) -> None:
        mark_run_day(db, "2024-03-04")
        # No trades inserted for this day
        days = get_daily_pl(db, "2024-03-04", "2024-03-04")
        assert len(days) == 1
        assert days[0]["color"] == "blue"
        assert days[0]["trade_count"] == 0
        assert days[0]["ran"] is True

    def test_non_run_day_omitted(self, db: DbConn) -> None:
        mark_run_day(db, "2024-03-05")
        # 2024-03-06 is NOT a run day
        _add_trade_on(db, "2024-03-06", net_pnl=100.0)
        days = get_daily_pl(db, "2024-03-05", "2024-03-07")
        dates = [d["date"] for d in days]
        assert "2024-03-06" not in dates
        assert "2024-03-07" not in dates
        assert "2024-03-05" in dates

    def test_empty_date_range(self, db: DbConn) -> None:
        days = get_daily_pl(db, "2024-01-01", "2024-01-31")
        assert days == []

    def test_multi_day_range(self, db: DbConn) -> None:
        for date, pnl in [
            ("2024-04-01", 100.0),
            ("2024-04-02", -50.0),
            ("2024-04-03", 0.0),
        ]:
            mark_run_day(db, date)
            _add_trade_on(db, date, pnl)

        days = get_daily_pl(db, "2024-04-01", "2024-04-04")
        by_date = {d["date"]: d for d in days}

        assert by_date["2024-04-01"]["color"] == "green"
        assert by_date["2024-04-02"]["color"] == "red"
        assert by_date["2024-04-03"]["color"] == "blue"
        assert "2024-04-04" not in by_date

    def test_cumulative_net_pl(self, db: DbConn) -> None:
        """Multiple trades on same day sum to correct net_pl."""
        mark_run_day(db, "2024-05-10")
        _add_trade_on(db, "2024-05-10", net_pnl=80.0)
        _add_trade_on(db, "2024-05-10", net_pnl=-30.0)
        days = get_daily_pl(db, "2024-05-10", "2024-05-10")
        assert days[0]["net_pl"] == pytest.approx(50.0)
        assert days[0]["trade_count"] == 2
        assert days[0]["color"] == "green"

    def test_ran_field_is_always_true(self, db: DbConn) -> None:
        mark_run_day(db, "2024-06-01")
        days = get_daily_pl(db, "2024-06-01", "2024-06-01")
        assert days[0]["ran"] is True
