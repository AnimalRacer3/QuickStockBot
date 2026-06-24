"""Tests for scan window anchoring to a mocked Alpaca open."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from bot.alpaca.client import CalendarDay, ClockInfo
from bot.scanner.models import ScanWindow
from bot.scanner.window import get_scan_window, is_in_window
from tests.scanner.conftest import FakeScannerClient


def _utc(year: int, month: int, day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)


class TestGetScanWindow:
    def test_standard_open_window_start(self) -> None:
        """window_start = session_open (09:30 ET = 14:30 UTC in EST) - 1h = 13:30 UTC."""
        client = FakeScannerClient(
            clock=ClockInfo(
                timestamp="2024-01-02T08:30:00-05:00",
                is_open=False,
                next_open="",
                next_close="",
            ),
            calendar=[CalendarDay(date="2024-01-02", open_="09:30", close="16:00")],
        )
        window = get_scan_window(
            client, pre_open_lead_hours=1.0, scan_duration_hours=3.0
        )
        # EST: -5h → 09:30 ET = 14:30 UTC
        expected_open = _utc(2024, 1, 2, 14, 30)
        expected_start = expected_open - timedelta(hours=1)
        assert window.session_open == expected_open
        assert window.window_start == expected_start

    def test_window_duration(self) -> None:
        """window_end = window_start + scan_duration_hours."""
        client = FakeScannerClient(
            clock=ClockInfo(
                timestamp="2024-01-02T08:30:00-05:00",
                is_open=False,
                next_open="",
                next_close="",
            ),
            calendar=[CalendarDay(date="2024-01-02", open_="09:30", close="16:00")],
        )
        window = get_scan_window(
            client, pre_open_lead_hours=1.0, scan_duration_hours=3.0
        )
        duration = window.window_end - window.window_start
        assert duration == timedelta(hours=3)

    def test_custom_lead_hours(self) -> None:
        client = FakeScannerClient(
            clock=ClockInfo(
                timestamp="2024-01-02T08:30:00-05:00",
                is_open=False,
                next_open="",
                next_close="",
            ),
            calendar=[CalendarDay(date="2024-01-02", open_="09:30", close="16:00")],
        )
        window = get_scan_window(
            client, pre_open_lead_hours=2.0, scan_duration_hours=4.0
        )
        expected_open = _utc(2024, 1, 2, 14, 30)
        assert window.window_start == expected_open - timedelta(hours=2)
        assert window.window_end - window.window_start == timedelta(hours=4)

    def test_fallback_when_no_calendar(self) -> None:
        """Falls back to 09:30 ET when calendar returns empty list."""
        client = FakeScannerClient(
            clock=ClockInfo(
                timestamp="2024-01-02T08:30:00-05:00",
                is_open=False,
                next_open="",
                next_close="",
            ),
            calendar=[],
        )
        window = get_scan_window(
            client, pre_open_lead_hours=1.0, scan_duration_hours=3.0
        )
        # Should still produce a valid window
        assert window.window_start < window.session_open < window.window_end

    def test_early_close_day(self) -> None:
        """Half-day: session opens at 09:30 and closes at 13:00 (not relevant for window start)."""
        client = FakeScannerClient(
            clock=ClockInfo(
                timestamp="2024-11-29T08:30:00-05:00",
                is_open=False,
                next_open="",
                next_close="",
            ),
            calendar=[CalendarDay(date="2024-11-29", open_="09:30", close="13:00")],
        )
        window = get_scan_window(
            client, pre_open_lead_hours=1.0, scan_duration_hours=3.0
        )
        # EDT is -4h in summer; Nov 29 is standard time (-5h)
        expected_open = _utc(2024, 11, 29, 14, 30)
        assert window.session_open == expected_open

    def test_dst_summer_open(self) -> None:
        """EDT (summer): 09:30 ET = 13:30 UTC."""
        client = FakeScannerClient(
            clock=ClockInfo(
                timestamp="2024-06-03T08:30:00-04:00",
                is_open=False,
                next_open="",
                next_close="",
            ),
            calendar=[CalendarDay(date="2024-06-03", open_="09:30", close="16:00")],
        )
        window = get_scan_window(
            client, pre_open_lead_hours=1.0, scan_duration_hours=3.0
        )
        expected_open = _utc(2024, 6, 3, 13, 30)
        assert window.session_open == expected_open


class TestIsInWindow:
    def _make_window(self) -> ScanWindow:
        return ScanWindow(
            window_start=_utc(2024, 1, 2, 13, 30),
            window_end=_utc(2024, 1, 2, 16, 30),
            session_open=_utc(2024, 1, 2, 14, 30),
        )

    def test_inside_window(self) -> None:
        w = self._make_window()
        assert is_in_window(_utc(2024, 1, 2, 14, 0), w) is True

    def test_at_window_start(self) -> None:
        w = self._make_window()
        assert is_in_window(_utc(2024, 1, 2, 13, 30), w) is True

    def test_before_window(self) -> None:
        w = self._make_window()
        assert is_in_window(_utc(2024, 1, 2, 13, 29), w) is False

    def test_at_window_end_exclusive(self) -> None:
        w = self._make_window()
        assert is_in_window(_utc(2024, 1, 2, 16, 30), w) is False

    def test_after_window(self) -> None:
        w = self._make_window()
        assert is_in_window(_utc(2024, 1, 2, 17, 0), w) is False
