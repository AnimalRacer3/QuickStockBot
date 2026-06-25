"""Relay round-trip reachability check for the setup wizard."""

from __future__ import annotations

import asyncio
import dataclasses
import hashlib
import hmac
import json
import uuid
from typing import Any, Callable


@dataclasses.dataclass(frozen=True)
class ReachabilityResult:
    success: bool
    bot_url: str
    message: str


def _compute_proof(nonce: str, password: str) -> str:
    return hmac.new(
        password.encode("utf-8"),
        nonce.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


async def _check_relay_async(
    relay_url: str,
    bot_id: str,
    license_key: str,
    connection_password: str,
    socket_factory: Callable[..., Any] | None = None,
    timeout: float = 10.0,
) -> ReachabilityResult:
    """
    Perform the auth + register handshake with the relay.

    The *socket_factory* parameter accepts the same interface as
    ``websockets.connect`` (async context manager returning a WebSocket).
    Inject a stub in tests to avoid real network calls.
    """
    try:
        import websockets  # type: ignore[import-untyped]

        connect = socket_factory or websockets.connect

        async with asyncio.timeout(timeout):
            async with connect(relay_url) as ws:
                raw = await ws.recv()
                msg = json.loads(raw)
                if msg.get("type") != "auth_challenge":
                    return ReachabilityResult(
                        success=False,
                        bot_url="",
                        message=(
                            f"Expected auth_challenge from relay, got: {msg.get('type')!r}"
                        ),
                    )

                nonce: str = msg["payload"]["nonce"]
                proof = _compute_proof(nonce, connection_password)

                await ws.send(
                    json.dumps(
                        {
                            "type": "register",
                            "id": str(uuid.uuid4()),
                            "payload": {
                                "bot_id": bot_id,
                                "license_key": license_key,
                                "connection_password_proof": proof,
                                "version": "0.1.0",
                            },
                        }
                    )
                )

                bot_url = _build_bot_url(relay_url, bot_id)
                return ReachabilityResult(
                    success=True,
                    bot_url=bot_url,
                    message="Bot is reachable from the relay.",
                )

    except TimeoutError:
        return ReachabilityResult(
            success=False,
            bot_url="",
            message="Relay connection timed out. Check the relay URL and your network.",
        )
    except Exception as exc:
        return ReachabilityResult(
            success=False,
            bot_url="",
            message=f"Connection failed: {exc}",
        )


def check_relay(
    relay_url: str,
    bot_id: str,
    license_key: str,
    connection_password: str,
    socket_factory: Callable[..., Any] | None = None,
    timeout: float = 10.0,
) -> ReachabilityResult:
    """Synchronous wrapper around ``_check_relay_async``."""
    return asyncio.run(
        _check_relay_async(
            relay_url=relay_url,
            bot_id=bot_id,
            license_key=license_key,
            connection_password=connection_password,
            socket_factory=socket_factory,
            timeout=timeout,
        )
    )


def _build_bot_url(relay_url: str, bot_id: str) -> str:
    """Derive the stable HTTPS bot URL from the relay WebSocket URL."""
    http_base = relay_url.replace("wss://", "https://").replace("ws://", "http://")
    for suffix in ("/ws/", "/ws"):
        if http_base.endswith(suffix):
            http_base = http_base[: -len(suffix)]
            break
    return f"{http_base}/bots/{bot_id}"
