"""Scan window control anchored to Alpaca's trading calendar."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from bot.alpaca.client import MarketClient
from bot.scanner.models import ScanWindow

# Eastern offset constants (handled via fixed offsets; no pytz dependency).
# Alpaca calendar open/close times are "HH:MM" in US/Eastern.
_ET_STANDARD = timezone(timedelta(hours=-5))  # EST
_ET_DAYLIGHT = timezone(timedelta(hours=-4))  # EDT


def _et_offset(dt: datetime) -> timezone:
    """Return the US/Eastern UTC offset for *dt* (DST-aware approximation).

    Uses the US DST rule: second Sunday of March → first Sunday of November.
    Accurate for all years; no external dependency.
    """
    year = dt.year

    def _nth_sunday(month: int, n: int) -> datetime:
        # First day of month
        first = datetime(year, month, 1, tzinfo=timezone.utc)
        # Day-of-week of the 1st (0=Mon … 6=Sun)
        dow = first.weekday()  # Mon=0 … Sun=6
        days_to_sun = (6 - dow) % 7  # days until first Sunday
        first_sunday = first + timedelta(days=days_to_sun)
        return first_sunday + timedelta(weeks=n - 1)

    dst_start = _nth_sunday(3, 2)  # 2nd Sunday March  02:00 ET
    dst_end = _nth_sunday(11, 1)  # 1st Sunday Nov    02:00 ET

    # Compare on date portion
    d = datetime(dt.year, dt.month, dt.day, tzinfo=timezone.utc)
    if dst_start <= d < dst_end:
        return _ET_DAYLIGHT
    return _ET_STANDARD


def _parse_et_time(date_str: str, time_str: str) -> datetime:
    """Parse "YYYY-MM-DD" + "HH:MM" (Eastern) → UTC datetime."""
    naive = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    et_off = _et_offset(naive)
    et_aware = naive.replace(tzinfo=et_off)
    return et_aware.astimezone(timezone.utc)


def get_scan_window(
    client: MarketClient,
    pre_open_lead_hours: float = 1.0,
    scan_duration_hours: float = 3.0,
) -> ScanWindow:
    """Return today's scan window anchored to the actual session open.

    Fetches today's date from /v2/clock, then looks up the session open
    from /v2/calendar.  Falls back to 09:30 ET if no calendar entry found.

    Window:
      window_start = session_open − pre_open_lead_hours
      window_end   = window_start + scan_duration_hours
    """
    clock = client.get_clock()
    # Alpaca timestamp is ISO-8601; strip to date portion
    today_str = clock.timestamp[:10]  # "YYYY-MM-DD"

    calendar = client.get_calendar(start=today_str, end=today_str)

    if calendar:
        day = calendar[0]
        session_open = _parse_et_time(day.date, day.open)
    else:
        # Fallback: standard 09:30 ET
        et_off = _et_offset(datetime.now(tz=timezone.utc))
        naive = datetime.strptime(f"{today_str} 09:30", "%Y-%m-%d %H:%M")
        session_open = naive.replace(tzinfo=et_off).astimezone(timezone.utc)

    window_start = session_open - timedelta(hours=pre_open_lead_hours)
    window_end = window_start + timedelta(hours=scan_duration_hours)

    return ScanWindow(
        window_start=window_start,
        window_end=window_end,
        session_open=session_open,
    )


def is_in_window(now: datetime, window: ScanWindow) -> bool:
    """True when *now* (UTC) falls within the scan window."""
    return window.window_start <= now < window.window_end
