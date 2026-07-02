from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from trader.market_calendar import MarketCalendar, build_session_info

TZ = ZoneInfo("America/New_York")


def test_build_session_info_normal_day_is_not_early_close():
    day = date(2024, 6, 3)
    market_open = datetime(2024, 6, 3, 9, 30, tzinfo=TZ)
    market_close = datetime(2024, 6, 3, 16, 0, tzinfo=TZ)
    session = build_session_info(day, market_open, market_close, TZ)
    assert session.is_open is True
    assert session.is_early_close is False


def test_build_session_info_early_close_day():
    day = date(2024, 11, 29)  # e.g. day after Thanksgiving, 1pm close
    market_open = datetime(2024, 11, 29, 9, 30, tzinfo=TZ)
    market_close = datetime(2024, 11, 29, 13, 0, tzinfo=TZ)
    session = build_session_info(day, market_open, market_close, TZ)
    assert session.is_early_close is True


def test_force_close_and_cutoff_times_derive_from_actual_close_not_hardcoded_16h():
    day = date(2024, 11, 29)
    market_open = datetime(2024, 11, 29, 9, 30, tzinfo=TZ)
    market_close = datetime(2024, 11, 29, 13, 0, tzinfo=TZ)
    session = build_session_info(day, market_open, market_close, TZ)

    force_close = session.force_close_time(offset_minutes=5)
    assert force_close == market_close - timedelta(minutes=5)
    assert force_close.hour == 12 and force_close.minute == 55

    z_hour = session.z_hour_cutoff_time(z_hour_cutoff=1.0)
    assert z_hour == market_close - timedelta(hours=1)
    assert z_hour.hour == 12

    no_trade_cutoff = session.no_trade_cutoff_time(no_trade_cutoff_hours=2.0)
    assert no_trade_cutoff == market_open + timedelta(hours=2)


class _FakeCalendarEntry:
    def __init__(self, open_time, close_time):
        self.open = open_time
        self.close = close_time


class _FakeTime:
    def __init__(self, hour, minute):
        self.hour = hour
        self.minute = minute
        self.second = 0


class _FakeTradingClient:
    def __init__(self, entries):
        self._entries = entries

    def get_calendar(self, request):
        return self._entries


def test_market_calendar_reports_closed_on_holiday_weekend():
    calendar = MarketCalendar(_FakeTradingClient([]), tz_name="America/New_York")
    session = calendar.get_session_info(date(2024, 12, 25))  # Christmas, no calendar entry
    assert session.is_open is False


def test_market_calendar_reports_open_with_normal_hours():
    entries = [_FakeCalendarEntry(_FakeTime(9, 30), _FakeTime(16, 0))]
    calendar = MarketCalendar(_FakeTradingClient(entries), tz_name="America/New_York")
    session = calendar.get_session_info(date(2024, 6, 3))
    assert session.is_open is True
    assert session.is_early_close is False
    assert session.market_open.hour == 9 and session.market_open.minute == 30
    assert session.market_close.hour == 16


def test_market_calendar_detects_early_close_from_calendar_entry():
    entries = [_FakeCalendarEntry(_FakeTime(9, 30), _FakeTime(13, 0))]
    calendar = MarketCalendar(_FakeTradingClient(entries), tz_name="America/New_York")
    session = calendar.get_session_info(date(2024, 11, 29))
    assert session.is_open is True
    assert session.is_early_close is True
