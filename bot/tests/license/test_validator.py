"""
Section 15 — License validation, grace-period gating, live-mode confirmation,
and account-equity / PDT notices.

All network calls are replaced by FakeHttpClient or FakeNetworkError so these
tests are fully offline.
"""

from __future__ import annotations

import json
import sqlite3
import time
from typing import Any

import httpx
import pytest

from bot.control.connection import DbConn
from bot.control.handlers import handle_get_state, handle_update_settings
from bot.license.validator import (
    GRACE_PERIOD_SECONDS,
    LicenseValidator,
)

# ─── In-memory DB fixture ─────────────────────────────────────────────────────

_SCHEMA_SQL = """
CREATE TABLE settings (
  key        TEXT    PRIMARY KEY,
  value      TEXT    NOT NULL,
  updated_at INTEGER NOT NULL
);
"""


@pytest.fixture()
def db() -> DbConn:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA_SQL)
    conn.commit()
    return DbConn(conn, pg=False)


# ─── Fake HTTP helpers ────────────────────────────────────────────────────────


class _FakeResponse:
    def __init__(self, data: dict, status_code: int = 200) -> None:
        self._data = data
        self.status_code = status_code

    def json(self) -> dict:
        return self._data

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                "error",
                request=httpx.Request("GET", "http://test"),
                response=httpx.Response(self.status_code),
            )


class FakeHttpClient:
    """Injects a predetermined response or exception into LicenseValidator."""

    def __init__(self, response: dict | Exception) -> None:
        self._response = response

    def get(self, url: str, **kwargs: Any) -> _FakeResponse:
        if isinstance(self._response, Exception):
            raise self._response
        return _FakeResponse(self._response)


def _seed_last_valid(db: DbConn, seconds_ago: float) -> None:
    """Store a last-valid timestamp *seconds_ago* seconds in the past."""
    ts = time.time() - seconds_ago
    now = int(time.time())
    db.execute(
        "INSERT INTO settings (key, value, updated_at) VALUES (%s, %s, %s)"
        " ON CONFLICT (key) DO UPDATE SET"
        " value = EXCLUDED.value, updated_at = EXCLUDED.updated_at",
        ("_license_last_valid_ts", str(ts), now),
    )
    db.commit()


def _make_validator(db: DbConn, response: dict | Exception) -> LicenseValidator:
    return LicenseValidator(
        validate_url="https://api.example.com/validate",
        license_key="QSB-TEST-0000-0000-0000",
        db=db,
        http_client=FakeHttpClient(response),
    )


# ─── Core validation scenarios ────────────────────────────────────────────────


class TestActiveStatus:
    def test_active_allows_trading(self, db: DbConn) -> None:
        v = _make_validator(db, {"status": "active"})
        status = v.check_once()
        assert status.state == "active"
        assert status.trading_allowed is True

    def test_active_persists_last_valid_ts(self, db: DbConn) -> None:
        v = _make_validator(db, {"status": "active"})
        before = time.time()
        v.check_once()
        row = db.execute(
            "SELECT value FROM settings WHERE key = '_license_last_valid_ts'"
        ).fetchone()
        assert row is not None
        assert float(row["value"]) >= before

    def test_active_updates_cached_state(self, db: DbConn) -> None:
        v = _make_validator(db, {"status": "active"})
        v.check_once()
        assert v.current_state().state == "active"
        allowed, reason = v.trading_allowed()
        assert allowed is True
        assert "valid" in reason


class TestRevokedStatus:
    def test_revoked_within_grace_allows_trading(self, db: DbConn) -> None:
        _seed_last_valid(
            db, seconds_ago=1 * 24 * 3600
        )  # 1 day ago — within 30-day grace
        v = _make_validator(db, {"status": "revoked"})
        status = v.check_once()
        assert status.state == "revoked"
        assert status.trading_allowed is True
        assert "grace" in status.reason

    def test_revoked_past_grace_stops_trading(self, db: DbConn) -> None:
        _seed_last_valid(db, seconds_ago=31 * 24 * 3600)  # 31 days ago — past grace
        v = _make_validator(db, {"status": "revoked"})
        status = v.check_once()
        assert status.state == "revoked"
        assert status.trading_allowed is False
        assert "expired" in status.reason

    def test_revoked_without_last_valid_stops_trading(self, db: DbConn) -> None:
        # Never had a successful validation
        v = _make_validator(db, {"status": "revoked"})
        status = v.check_once()
        assert status.state == "revoked"
        assert status.trading_allowed is False

    def test_revoked_exactly_at_grace_boundary_stops_trading(self, db: DbConn) -> None:
        # last_valid_ts is exactly GRACE_PERIOD_SECONDS ago → outside window
        _seed_last_valid(db, seconds_ago=GRACE_PERIOD_SECONDS)
        v = _make_validator(db, {"status": "revoked"})
        status = v.check_once()
        assert status.trading_allowed is False


class TestOfflineStatus:
    def test_offline_within_grace_allows_trading(self, db: DbConn) -> None:
        _seed_last_valid(db, seconds_ago=1 * 24 * 3600)  # 1 day ago
        v = _make_validator(db, httpx.ConnectError("network unreachable"))
        status = v.check_once()
        assert status.state == "offline"
        assert status.trading_allowed is True
        assert "grace" in status.reason

    def test_offline_past_grace_stops_trading(self, db: DbConn) -> None:
        _seed_last_valid(db, seconds_ago=31 * 24 * 3600)  # 31 days ago
        v = _make_validator(db, httpx.ConnectError("network unreachable"))
        status = v.check_once()
        assert status.state == "offline"
        assert status.trading_allowed is False

    def test_offline_no_prior_validation_stops_trading(self, db: DbConn) -> None:
        v = _make_validator(db, httpx.ConnectError("network unreachable"))
        status = v.check_once()
        assert status.state == "offline"
        assert status.trading_allowed is False

    def test_offline_state_is_persisted_to_db(self, db: DbConn) -> None:
        _seed_last_valid(db, seconds_ago=1 * 24 * 3600)
        v = _make_validator(db, httpx.ConnectError("network unreachable"))
        v.check_once()
        row = db.execute(
            "SELECT value FROM settings WHERE key = '_license_cached_status'"
        ).fetchone()
        assert row and row["value"] == "offline"


class TestCachedStateRestore:
    def test_loads_cached_state_on_init(self, db: DbConn) -> None:
        # First validator writes active state
        v1 = _make_validator(db, {"status": "active"})
        v1.check_once()

        # Second validator (new instance, same DB) should restore "active" without network
        v2 = LicenseValidator(
            validate_url="https://api.example.com/validate",
            license_key="QSB-TEST-0000-0000-0000",
            db=db,
            http_client=FakeHttpClient(Exception("should not be called")),
        )
        assert v2.current_state().state == "active"
        assert v2.current_state().trading_allowed is True

    def test_unknown_state_before_any_check(self, db: DbConn) -> None:
        v = LicenseValidator(
            validate_url="https://api.example.com/validate",
            license_key="key",
            db=db,
            http_client=FakeHttpClient({"status": "active"}),
        )
        assert v.current_state().state == "unknown"
        assert v.current_state().trading_allowed is False


# ─── Live-mode confirmation gate ──────────────────────────────────────────────

# Minimal DB fixture for handler tests (mirrors control/conftest.py schema)
_HANDLER_SCHEMA = """
CREATE TABLE settings (
  key        TEXT    PRIMARY KEY,
  value      TEXT    NOT NULL,
  updated_at INTEGER NOT NULL
);

CREATE TABLE active_tickers (
  symbol            TEXT    PRIMARY KEY,
  price             REAL    NOT NULL,
  volume            REAL    NOT NULL,
  rsi               REAL,
  macd              REAL,
  signal            REAL,
  ema_short         REAL,
  ema_long          REAL,
  state             TEXT    NOT NULL,
  updated_at        INTEGER NOT NULL,
  gap_pct           REAL,
  rvol              REAL,
  float_shares      INTEGER,
  unknown_float     INTEGER NOT NULL DEFAULT 0,
  scanner_tradable  INTEGER NOT NULL DEFAULT 1,
  pct_change        REAL,
  macd_state_json   TEXT,
  pattern_tags_json TEXT,
  pattern_sig_json  TEXT,
  role              TEXT,
  score             REAL
);
"""

_HANDLER_DEFAULTS = [
    ("paper_trading", "true"),
    ("broker", "alpaca"),
    ("max_positions", "5"),
    ("risk_per_trade_pct", "1.0"),
    ("daily_risk_pct", "5.0"),
    ("risk_override_enabled", "false"),
    ("min_score", "60.0"),
    ("auto_trade", "false"),
    ("macd_fast", "12"),
    ("macd_slow", "26"),
    ("macd_signal", "9"),
    ("log_level", "info"),
    ("bot_id", "test-bot"),
    ("relay_url", "wss://relay.example.com"),
    ("license_key", "QSB-TEST"),
]


@pytest.fixture()
def handler_db() -> DbConn:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(_HANDLER_SCHEMA)
    now = int(time.time())
    conn.executemany(
        "INSERT INTO settings (key, value, updated_at) VALUES (?, ?, ?) ON CONFLICT (key) DO NOTHING",
        [(k, v, now) for k, v in _HANDLER_DEFAULTS],
    )
    conn.commit()
    return DbConn(conn, pg=False)


class TestLiveModeConfirmation:
    def test_enabling_live_without_confirmation_raises(
        self, handler_db: DbConn
    ) -> None:
        with pytest.raises(ValueError, match="live_mode_confirmation_required"):
            handle_update_settings(handler_db, {"patch": {"paper_trading": False}})

    def test_enabling_live_with_confirmation_succeeds(self, handler_db: DbConn) -> None:
        result = handle_update_settings(
            handler_db,
            {"patch": {"paper_trading": False, "live_mode_confirmed": True}},
        )
        assert result["paper_trading"] is False

    def test_confirmation_flag_not_persisted(self, handler_db: DbConn) -> None:
        handle_update_settings(
            handler_db,
            {"patch": {"paper_trading": False, "live_mode_confirmed": True}},
        )
        row = handler_db.execute(
            "SELECT value FROM settings WHERE key = 'live_mode_confirmed'"
        ).fetchone()
        assert row is None  # must not be written to DB

    def test_staying_in_paper_mode_does_not_require_confirmation(
        self, handler_db: DbConn
    ) -> None:
        result = handle_update_settings(handler_db, {"patch": {"paper_trading": True}})
        assert result["paper_trading"] is True

    def test_other_settings_update_without_confirmation(
        self, handler_db: DbConn
    ) -> None:
        result = handle_update_settings(handler_db, {"patch": {"max_positions": 3}})
        assert result["max_positions"] == 3


# ─── Notices in state ─────────────────────────────────────────────────────────


class TestNoticesInState:
    def test_account_equity_notice_always_present(self, handler_db: DbConn) -> None:
        result = handle_get_state(handler_db, {})
        types = {n["type"] for n in result["notices"]}
        assert "account_equity" in types

    def test_pdt_framework_notice_has_expected_fields(self, handler_db: DbConn) -> None:
        result = handle_get_state(handler_db, {})
        notice = next(n for n in result["notices"] if n["type"] == "account_equity")
        fw = notice["pdt_framework"]
        assert fw["effective_date"] == "2026-06-04"
        assert fw["min_account_equity_notice"] == 2000.0
        assert fw["old_pdt_rule_eliminated"] is True
        assert fw["broker_may_still_use_old_rules"] is True
        assert "2027-10-20" in fw["broker_migration_deadline"]

    def test_live_mode_notice_appears_when_live(self, handler_db: DbConn) -> None:
        handle_update_settings(
            handler_db,
            {"patch": {"paper_trading": False, "live_mode_confirmed": True}},
        )
        result = handle_get_state(handler_db, {})
        types = {n["type"] for n in result["notices"]}
        assert "live_mode" in types

    def test_no_live_mode_notice_in_paper_mode(self, handler_db: DbConn) -> None:
        result = handle_get_state(handler_db, {})
        types = {n["type"] for n in result["notices"]}
        assert "live_mode" not in types

    def test_pdt_restricted_notice_appears_when_flag_active(
        self, handler_db: DbConn
    ) -> None:
        account_snapshot = {
            "equity": 1500.0,
            "buying_power": 3000.0,
            "cash": 1500.0,
            "portfolio_value": 1500.0,
            "pattern_day_trader": True,
            "day_trade_count": 4,
            "day_trading_buying_power": 0.0,
            "is_pdt_restricted": True,
        }
        now = int(time.time())
        handler_db.execute(
            "INSERT INTO settings (key, value, updated_at) VALUES (?, ?, ?) ON CONFLICT (key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at",
            ("_account_snapshot", json.dumps(account_snapshot), now),
        )
        handler_db.commit()
        result = handle_get_state(handler_db, {})
        types = {n["type"] for n in result["notices"]}
        assert "pdt_restricted" in types
        assert "account_equity" in types

    def test_no_pdt_restricted_notice_when_not_flagged(
        self, handler_db: DbConn
    ) -> None:
        account_snapshot = {
            "equity": 50000.0,
            "buying_power": 100000.0,
            "cash": 50000.0,
            "portfolio_value": 50000.0,
            "pattern_day_trader": False,
            "day_trade_count": 0,
            "day_trading_buying_power": 200000.0,
            "is_pdt_restricted": False,
        }
        now = int(time.time())
        handler_db.execute(
            "INSERT INTO settings (key, value, updated_at) VALUES (?, ?, ?) ON CONFLICT (key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at",
            ("_account_snapshot", json.dumps(account_snapshot), now),
        )
        handler_db.commit()
        result = handle_get_state(handler_db, {})
        types = {n["type"] for n in result["notices"]}
        assert "pdt_restricted" not in types

    def test_license_notice_appears_when_revoked(self, handler_db: DbConn) -> None:
        now = int(time.time())
        for key, value in [
            ("_license_cached_status", "revoked"),
            ("_license_trading_allowed", "true"),
            ("_license_reason", "license revoked — grace period active"),
        ]:
            handler_db.execute(
                "INSERT INTO settings (key, value, updated_at) VALUES (?, ?, ?) ON CONFLICT (key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at",
                (key, value, now),
            )
        handler_db.commit()
        result = handle_get_state(handler_db, {})
        lic_notice = next(
            (n for n in result["notices"] if n["type"] == "license"), None
        )
        assert lic_notice is not None
        assert lic_notice["trading_allowed"] is True
        assert lic_notice["severity"] == "warning"

    def test_license_error_notice_when_trading_blocked(
        self, handler_db: DbConn
    ) -> None:
        now = int(time.time())
        for key, value in [
            ("_license_cached_status", "revoked"),
            ("_license_trading_allowed", "false"),
            (
                "_license_reason",
                "license revoked — grace period expired, trading stopped",
            ),
        ]:
            handler_db.execute(
                "INSERT INTO settings (key, value, updated_at) VALUES (?, ?, ?) ON CONFLICT (key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at",
                (key, value, now),
            )
        handler_db.commit()
        result = handle_get_state(handler_db, {})
        lic_notice = next(
            (n for n in result["notices"] if n["type"] == "license"), None
        )
        assert lic_notice is not None
        assert lic_notice["trading_allowed"] is False
        assert lic_notice["severity"] == "error"

    def test_no_license_notice_when_active(self, handler_db: DbConn) -> None:
        now = int(time.time())
        for key, value in [
            ("_license_cached_status", "active"),
            ("_license_trading_allowed", "true"),
            ("_license_reason", "license valid and active"),
        ]:
            handler_db.execute(
                "INSERT INTO settings (key, value, updated_at) VALUES (?, ?, ?) ON CONFLICT (key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at",
                (key, value, now),
            )
        handler_db.commit()
        result = handle_get_state(handler_db, {})
        types = {n["type"] for n in result["notices"]}
        assert "license" not in types
