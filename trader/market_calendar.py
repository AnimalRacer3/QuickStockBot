"""Market calendar/clock handling.

All close-relative times (force-close, z-hour cutoff, no-trade cutoff) are
derived from *today's actual* open/close from Alpaca's calendar -- never a
hardcoded 16:00 -- so early-close days (e.g. 1:00 PM) shift automatically.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class SessionInfo:
    """A single trading day's session window, in exchange-local time."""

    session_date: date
    market_open: datetime
    market_close: datetime
    is_open: bool
    is_early_close: bool

    def force_close_time(self, offset_minutes: float) -> datetime:
        return self.market_close - timedelta(minutes=offset_minutes)

    def z_hour_cutoff_time(self, z_hour_cutoff: float) -> datetime:
        """Time after which NEW entries are no longer allowed."""
        return self.market_close - timedelta(hours=z_hour_cutoff)

    def no_trade_cutoff_time(self, no_trade_cutoff_hours: float) -> datetime:
        """Time by which at least one entry must have happened, else shut down."""
        return self.market_open + timedelta(hours=no_trade_cutoff_hours)


def build_session_info(
    session_date: date,
    market_open: datetime,
    market_close: datetime,
    tz: ZoneInfo,
    is_open: bool = True,
) -> SessionInfo:
    """Pure function: build a SessionInfo from raw open/close, detecting early close.

    A "normal" NYSE session closes at 16:00 local time. Anything earlier is
    treated as an early close so callers can shift force-close/z-hour logic.
    """
    normal_close = market_open.replace(hour=16, minute=0, second=0, microsecond=0)
    is_early_close = market_close < normal_close
    return SessionInfo(
        session_date=session_date,
        market_open=market_open,
        market_close=market_close,
        is_open=is_open,
        is_early_close=is_early_close,
    )


class MarketCalendar:
    """Thin wrapper around Alpaca's TradingClient calendar/clock endpoints."""

    def __init__(self, trading_client: object, tz_name: str = "America/New_York"):
        self._client = trading_client
        self.tz = ZoneInfo(tz_name)

    def get_session_info(self, day: date) -> SessionInfo:
        from alpaca.trading.requests import GetCalendarRequest

        request = GetCalendarRequest(start=day, end=day)
        entries = self._client.get_calendar(request)  # type: ignore[attr-defined]
        if not entries:
            # Holiday or weekend: Alpaca returns no calendar entry for that date.
            midnight = datetime(day.year, day.month, day.day, tzinfo=self.tz)
            return SessionInfo(
                session_date=day,
                market_open=midnight,
                market_close=midnight,
                is_open=False,
                is_early_close=False,
            )

        entry = entries[0]
        market_open = _combine(day, entry.open, self.tz)
        market_close = _combine(day, entry.close, self.tz)
        return build_session_info(day, market_open, market_close, self.tz, is_open=True)

    def get_clock(self) -> object:
        return self._client.get_clock()  # type: ignore[attr-defined]


def _combine(day: date, time_obj: object, tz: ZoneInfo) -> datetime:
    """Combine an Alpaca calendar date + time-of-day into a tz-aware datetime."""
    return datetime(
        day.year, day.month, day.day,
        time_obj.hour, time_obj.minute, getattr(time_obj, "second", 0),
        tzinfo=tz,
    )
