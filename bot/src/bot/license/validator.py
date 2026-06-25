"""
License phone-home and grace-period enforcement (Section 15).

On startup and periodically, the bot calls the SaaS validation endpoint.
If the response is "active", the last-valid timestamp is updated in the DB.
On revocation or network failure, a 30-day grace window (measured from the
last successful validation) keeps trading alive; once the window expires,
trading is blocked until a valid response is received.
"""

from __future__ import annotations

import asyncio
import dataclasses
import logging
import sqlite3
import time
from typing import Literal

import httpx

logger = logging.getLogger(__name__)

GRACE_PERIOD_SECONDS: float = 30 * 24 * 3600  # 30 days

# DB keys (stored in the settings table)
_KEY_LAST_VALID_TS = "_license_last_valid_ts"
_KEY_STATUS = "_license_cached_status"
_KEY_TRADING_ALLOWED = "_license_trading_allowed"
_KEY_REASON = "_license_reason"

LicenseState = Literal["active", "revoked", "offline", "unknown"]


@dataclasses.dataclass(frozen=True)
class LicenseStatus:
    """Current license health as seen by the bot."""

    state: LicenseState
    trading_allowed: bool
    reason: str
    last_valid_ts: float | None  # epoch seconds of last "active" response; None if never


class LicenseValidator:
    """
    Validates the bot's license key against the SaaS endpoint and enforces
    the grace-period trading gate.

    Inject *http_client* in tests to mock the network call.
    """

    def __init__(
        self,
        validate_url: str,
        license_key: str,
        db: sqlite3.Connection,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._url = validate_url
        self._key = license_key
        self._db = db
        self._http = http_client or httpx.Client(timeout=10.0)
        # Restore any cached state so trading decisions are instant on restart
        self._state: LicenseStatus = self._load_cached()

    # ── Public API ──────────────────────────────────────────────────────────

    def check_once(self) -> LicenseStatus:
        """
        Phone home once, update the DB cache, and return the current status.

        Safe to call from a sync context (e.g., startup code). The async
        periodic loop calls this inside an executor if needed.
        """
        now = time.time()
        last_valid_ts = self._load_last_valid_ts()

        try:
            resp = self._http.get(self._url, params={"key": self._key})
            resp.raise_for_status()
            data: dict = resp.json()
            server_status: str | None = data.get("status")
        except Exception as exc:
            logger.warning("License validation network failure: %s", exc)
            return self._handle_offline(now, last_valid_ts)

        status = self._interpret(server_status, now, last_valid_ts)

        if server_status == "active":
            self._save_last_valid_ts(now)
        self._persist(status)
        self._state = status
        return status

    def current_state(self) -> LicenseStatus:
        """Return the most recently computed or cached status without a network call."""
        return self._state

    def trading_allowed(self) -> tuple[bool, str]:
        """Convenience accessor returning (allowed, reason)."""
        s = self._state
        return s.trading_allowed, s.reason

    async def run_periodic(self, interval_seconds: float = 86_400.0) -> None:
        """
        Async background loop: call check_once() every *interval_seconds*.

        Designed to run as an asyncio task alongside the bot's relay loop.
        """
        while True:
            try:
                self.check_once()
            except Exception as exc:
                logger.exception("Unexpected error in license periodic check: %s", exc)
            await asyncio.sleep(interval_seconds)

    # ── Internal helpers ────────────────────────────────────────────────────

    def _handle_offline(self, now: float, last_valid_ts: float | None) -> LicenseStatus:
        if last_valid_ts is not None and (now - last_valid_ts) < GRACE_PERIOD_SECONDS:
            status = LicenseStatus(
                state="offline",
                trading_allowed=True,
                reason="validation endpoint unreachable — offline within grace window, trading continues",
                last_valid_ts=last_valid_ts,
            )
        else:
            status = LicenseStatus(
                state="offline",
                trading_allowed=False,
                reason="validation endpoint unreachable — offline past grace window, trading stopped",
                last_valid_ts=last_valid_ts,
            )
        self._persist(status)
        self._state = status
        return status

    def _interpret(
        self, server_status: str | None, now: float, last_valid_ts: float | None
    ) -> LicenseStatus:
        if server_status == "active":
            return LicenseStatus(
                state="active",
                trading_allowed=True,
                reason="license valid and active",
                last_valid_ts=now,
            )

        if server_status in ("revoked", "expired"):
            if last_valid_ts is not None and (now - last_valid_ts) < GRACE_PERIOD_SECONDS:
                return LicenseStatus(
                    state="revoked",
                    trading_allowed=True,
                    reason=(
                        f"license {server_status} — grace period active, "
                        "trading continues until grace expires"
                    ),
                    last_valid_ts=last_valid_ts,
                )
            return LicenseStatus(
                state="revoked",
                trading_allowed=False,
                reason=f"license {server_status} — grace period expired, trading stopped",
                last_valid_ts=last_valid_ts,
            )

        return LicenseStatus(
            state="unknown",
            trading_allowed=False,
            reason=f"unexpected server status: {server_status!r}",
            last_valid_ts=last_valid_ts,
        )

    # ── DB persistence ──────────────────────────────────────────────────────

    def _load_last_valid_ts(self) -> float | None:
        row = self._db.execute(
            "SELECT value FROM settings WHERE key = ?", (_KEY_LAST_VALID_TS,)
        ).fetchone()
        if row and row[0]:
            try:
                return float(row[0])
            except (ValueError, TypeError):
                pass
        return None

    def _save_last_valid_ts(self, ts: float) -> None:
        now_int = int(time.time())
        self._db.execute(
            "INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, ?)",
            (_KEY_LAST_VALID_TS, str(ts), now_int),
        )
        self._db.commit()

    def _persist(self, status: LicenseStatus) -> None:
        now_int = int(time.time())
        pairs = [
            (_KEY_STATUS, status.state),
            (_KEY_TRADING_ALLOWED, "true" if status.trading_allowed else "false"),
            (_KEY_REASON, status.reason),
        ]
        for key, value in pairs:
            self._db.execute(
                "INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, ?)",
                (key, value, now_int),
            )
        self._db.commit()

    def _load_cached(self) -> LicenseStatus:
        rows = {
            r[0]: r[1]
            for r in self._db.execute(
                "SELECT key, value FROM settings WHERE key IN (?, ?, ?, ?)",
                (_KEY_STATUS, _KEY_TRADING_ALLOWED, _KEY_REASON, _KEY_LAST_VALID_TS),
            ).fetchall()
        }
        state: LicenseState = rows.get(_KEY_STATUS, "unknown")  # type: ignore[assignment]
        allowed_str = rows.get(_KEY_TRADING_ALLOWED, "false") or "false"
        trading_allowed = allowed_str.lower() in ("true", "1")
        reason = rows.get(_KEY_REASON) or "no validation performed yet"
        last_valid_str = rows.get(_KEY_LAST_VALID_TS)
        last_valid_ts: float | None = None
        if last_valid_str:
            try:
                last_valid_ts = float(last_valid_str)
            except (ValueError, TypeError):
                pass
        return LicenseStatus(
            state=state,
            trading_allowed=trading_allowed,
            reason=reason,
            last_valid_ts=last_valid_ts,
        )
