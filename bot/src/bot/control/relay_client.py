"""
Outbound WebSocket relay client.

Connects to the relay, authenticates via HMAC-SHA256, registers the bot,
dispatches incoming rpc_request frames to the control handlers, and streams
log + state_update frames. Auto-reconnects with exponential backoff.
"""

from __future__ import annotations

import asyncio
import datetime
import hashlib
import hmac
import json
import logging
import sqlite3
import uuid
from collections.abc import Callable
from typing import Any

import websockets
import websockets.exceptions

from bot.control.handlers import dispatch

logger = logging.getLogger(__name__)

VERSION = "0.1.0"
_LEVEL_ORDER = {"debug": 0, "info": 1, "warning": 2, "error": 3}


def compute_connection_proof(nonce: str, password: str) -> str:
    """HMAC-SHA256(key=password, msg=nonce) → hex string."""
    return hmac.new(
        password.encode("utf-8"),
        nonce.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


class RelayClient:
    """
    Manages the bot's outbound WebSocket connection to the relay server.

    Pass *socket_factory* to inject a mock during tests; defaults to
    ``websockets.connect``.
    """

    def __init__(
        self,
        url: str,
        bot_id: str,
        license_key: str,
        connection_password: str,
        db: sqlite3.Connection,
        socket_factory: Callable | None = None,
    ) -> None:
        self.url = url
        self.bot_id = bot_id
        self.license_key = license_key
        self.connection_password = connection_password
        self.db = db
        self._socket_factory: Callable = socket_factory or websockets.connect
        self._ws: Any = None
        self._log_filter: dict | None = None
        self._running = False
        self._backoff = 1.0

    # ── Public API ──────────────────────────────────────────────────────────

    async def run(self) -> None:
        """Run forever: connect → authenticate → dispatch → reconnect on error."""
        self._running = True
        while self._running:
            try:
                await self._run_session()
                self._backoff = 1.0
            except asyncio.CancelledError:
                break
            except Exception as exc:
                reason = self._parse_close_reason(exc)
                if reason and reason.startswith("AUTH_FAILED"):
                    logger.error(
                        "Relay authentication failed: %s\n"
                        "  Fix: check your .env file — BOT_ID, LICENSE_KEY, and CONNECTION_PASSWORD\n"
                        "  Detail: %s",
                        reason.removeprefix("AUTH_FAILED: ").removeprefix("AUTH_FAILED"),
                        exc,
                    )
                else:
                    logger.warning(
                        "Relay session ended: %s — retrying in %.0fs", exc, self._backoff
                    )
                await asyncio.sleep(self._backoff)
                self._backoff = min(self._backoff * 2, 60.0)

    def stop(self) -> None:
        self._running = False

    async def emit_log(
        self,
        category: str,
        level: str,
        message: str,
        payload: dict | None = None,
    ) -> None:
        """Push a log frame if a matching subscription is active."""
        if self._ws is None or self._log_filter is None:
            return
        categories = self._log_filter.get("categories", [])
        if categories and category not in categories:
            return
        min_level = self._log_filter.get("min_level", "info")
        if _LEVEL_ORDER.get(level, 0) < _LEVEL_ORDER.get(min_level, 1):
            return

        event: dict = {
            "timestamp": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "category": category,
            "message": message,
        }
        if payload:
            event["payload"] = payload

        await self._send({"type": "log", "id": str(uuid.uuid4()), "payload": event})

    async def emit_state_update(
        self, tickers: list[dict], account: dict | None = None
    ) -> None:
        """Push a state_update frame."""
        if self._ws is None:
            return
        body: dict = {"tickers": tickers}
        if account:
            body["account"] = account
        await self._send(
            {"type": "state_update", "id": str(uuid.uuid4()), "payload": body}
        )

    # ── Internal ────────────────────────────────────────────────────────────

    async def _run_session(self) -> None:
        async with self._socket_factory(self.url) as ws:
            self._ws = ws
            try:
                await self._authenticate(ws)
                logger.info(
                    "Connected to relay at %s (bot_id=%s)", self.url, self.bot_id
                )
                async for raw in ws:
                    msg = json.loads(raw)
                    if msg.get("type") == "rpc_request":
                        reply = self._dispatch_rpc(msg)
                        await ws.send(json.dumps(reply))
            finally:
                self._ws = None
                logger.info("Disconnected from relay.")

    async def _authenticate(self, ws: Any) -> None:
        raw = await ws.recv()
        msg = json.loads(raw)
        if msg.get("type") != "auth_challenge":
            raise RuntimeError(f"Expected auth_challenge, got {msg.get('type')!r}")

        nonce: str = msg["payload"]["nonce"]
        proof = compute_connection_proof(nonce, self.connection_password)

        await ws.send(
            json.dumps(
                {
                    "type": "register",
                    "id": str(uuid.uuid4()),
                    "payload": {
                        "bot_id": self.bot_id,
                        "license_key": self.license_key,
                        "connection_password_proof": proof,
                        "version": VERSION,
                    },
                }
            )
        )

    def _dispatch_rpc(self, msg: dict) -> dict:
        request_id: str = msg["id"]
        method: str = msg["payload"]["method"]
        params: dict = msg["payload"].get("params") or {}
        try:
            result = dispatch(method, self.db, params, self._on_log_subscribe)
            return {
                "type": "rpc_response",
                "id": request_id,
                "payload": {"result": result},
            }
        except KeyError:
            return self._error_response(
                request_id, "UNKNOWN_METHOD", f"Unknown method: {method}"
            )
        except ValueError as exc:
            return self._error_response(request_id, "INVALID_PARAMS", str(exc))
        except Exception as exc:
            logger.exception("Error handling RPC %s", method)
            return self._error_response(request_id, "INTERNAL", str(exc))

    def _on_log_subscribe(self, filter_params: dict) -> None:
        self._log_filter = filter_params

    @staticmethod
    def _parse_close_reason(exc: BaseException) -> str | None:
        """Extract the WebSocket close reason string from a websockets exception."""
        rcvd = getattr(exc, "rcvd", None)
        if rcvd is not None:
            return getattr(rcvd, "reason", None)
        return None

    async def _send(self, msg: dict) -> None:
        if self._ws is not None:
            await self._ws.send(json.dumps(msg))

    @staticmethod
    def _error_response(request_id: str, code: str, message: str) -> dict:
        return {
            "type": "rpc_response",
            "id": request_id,
            "payload": {"result": None, "error": {"code": code, "message": message}},
        }
