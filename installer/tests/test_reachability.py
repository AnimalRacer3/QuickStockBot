"""Tests for relay reachability check (stub relay, no real network)."""

from __future__ import annotations

import asyncio
import json

import pytest

from wizard.reachability import (
    ReachabilityResult,
    _build_bot_url,
    _check_relay_async,
    check_relay,
)

BOT_ID = "test-bot-id-1234"
LICENSE = "LIC-TEST-KEY"
PASSWORD = "test_password_x"
RELAY_URL = "wss://relay.example.com/ws"


def _challenge(nonce: str = "test-nonce") -> str:
    return json.dumps({"type": "auth_challenge", "payload": {"nonce": nonce}})


class _StubWs:
    """Minimal WebSocket stub: pre-loads inbound messages, records outbound."""

    def __init__(self, inbound: list[str]) -> None:
        self._q: asyncio.Queue[str] = asyncio.Queue()
        for msg in inbound:
            self._q.put_nowait(msg)
        self.sent: list[str] = []

    async def recv(self) -> str:
        return await self._q.get()

    async def send(self, data: str) -> None:
        self.sent.append(data)


def _factory(ws: _StubWs):
    """Return an async-context-manager socket factory wrapping *ws*."""

    class _CM:
        def __init__(self, url: str, **kw: object) -> None:
            pass

        async def __aenter__(self) -> _StubWs:
            return ws

        async def __aexit__(self, *args: object) -> None:
            pass

    return _CM


class _NeverConnects:
    """Factory that hangs forever — triggers timeout."""

    def __init__(self, url: str, **kw: object) -> None:
        pass

    async def __aenter__(self) -> None:
        await asyncio.sleep(999)

    async def __aexit__(self, *args: object) -> None:
        pass


# ── async tests ───────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_successful_handshake() -> None:
    ws = _StubWs([_challenge("my-nonce")])
    result = await _check_relay_async(
        relay_url=RELAY_URL,
        bot_id=BOT_ID,
        license_key=LICENSE,
        connection_password=PASSWORD,
        socket_factory=_factory(ws),
    )
    assert result.success is True
    assert BOT_ID in result.bot_url
    assert "reachable" in result.message


@pytest.mark.anyio
async def test_register_frame_sent_after_challenge() -> None:
    ws = _StubWs([_challenge("nonce-abc")])
    await _check_relay_async(
        relay_url=RELAY_URL,
        bot_id=BOT_ID,
        license_key=LICENSE,
        connection_password=PASSWORD,
        socket_factory=_factory(ws),
    )
    assert len(ws.sent) == 1
    sent = json.loads(ws.sent[0])
    assert sent["type"] == "register"
    assert sent["payload"]["bot_id"] == BOT_ID
    assert sent["payload"]["license_key"] == LICENSE


@pytest.mark.anyio
async def test_wrong_first_message_returns_failure() -> None:
    ws = _StubWs([json.dumps({"type": "unexpected_type"})])
    result = await _check_relay_async(
        relay_url=RELAY_URL,
        bot_id=BOT_ID,
        license_key=LICENSE,
        connection_password=PASSWORD,
        socket_factory=_factory(ws),
    )
    assert result.success is False
    assert "auth_challenge" in result.message


@pytest.mark.anyio
async def test_timeout_returns_failure() -> None:
    result = await _check_relay_async(
        relay_url=RELAY_URL,
        bot_id=BOT_ID,
        license_key=LICENSE,
        connection_password=PASSWORD,
        socket_factory=_NeverConnects,
        timeout=0.05,
    )
    assert result.success is False
    assert "timed out" in result.message.lower()


@pytest.mark.anyio
async def test_connection_exception_returns_failure() -> None:
    class _ErrorFactory:
        def __init__(self, url: str, **kw: object) -> None:
            pass

        async def __aenter__(self) -> None:
            raise ConnectionRefusedError("refused")

        async def __aexit__(self, *args: object) -> None:
            pass

    result = await _check_relay_async(
        relay_url=RELAY_URL,
        bot_id=BOT_ID,
        license_key=LICENSE,
        connection_password=PASSWORD,
        socket_factory=_ErrorFactory,
    )
    assert result.success is False
    assert "refused" in result.message.lower() or "failed" in result.message.lower()


# ── bot URL builder ───────────────────────────────────────────────────────────


def test_build_url_strips_ws_suffix() -> None:
    url = _build_bot_url("wss://relay.quickstockbot.com/ws", "abc-123")
    assert url == "https://relay.quickstockbot.com/bots/abc-123"


def test_build_url_strips_ws_trailing_slash() -> None:
    url = _build_bot_url("wss://relay.example.com/ws/", "xyz")
    assert url == "https://relay.example.com/bots/xyz"


def test_build_url_plain_ws() -> None:
    url = _build_bot_url("ws://localhost:8080/ws", "my-bot")
    assert url == "http://localhost:8080/bots/my-bot"


def test_build_url_no_suffix() -> None:
    url = _build_bot_url("wss://relay.example.com", "bot-99")
    assert url == "https://relay.example.com/bots/bot-99"


# ── synchronous wrapper ───────────────────────────────────────────────────────


def test_check_relay_sync_wrapper_success() -> None:
    ws = _StubWs([_challenge()])
    result = check_relay(
        relay_url=RELAY_URL,
        bot_id=BOT_ID,
        license_key=LICENSE,
        connection_password=PASSWORD,
        socket_factory=_factory(ws),
        timeout=5.0,
    )
    assert result.success is True


def test_check_relay_sync_wrapper_returns_dataclass() -> None:
    ws = _StubWs([_challenge()])
    result = check_relay(
        relay_url=RELAY_URL,
        bot_id=BOT_ID,
        license_key=LICENSE,
        connection_password=PASSWORD,
        socket_factory=_factory(ws),
    )
    assert isinstance(result, ReachabilityResult)
