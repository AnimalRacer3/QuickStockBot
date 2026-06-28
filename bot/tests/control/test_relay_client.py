"""
Relay client tests: auth, reconnect, log stream, localhost binding.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import sqlite3
import uuid

import pytest

from bot.control.relay_client import RelayClient, compute_connection_proof
from tests.control.conftest import insert_ticker
from tests.control.mock_relay import MockRelaySocket, MockSocketFactory

# ─── Helpers ──────────────────────────────────────────────────────────────────


def _client(db: sqlite3.Connection, factory: MockSocketFactory, **kw) -> RelayClient:
    return RelayClient(
        url="ws://mock",
        bot_id=kw.get("bot_id", "test-bot"),
        license_key=kw.get("license_key", "test-lic"),
        connection_password=kw.get("connection_password", "test-password"),
        db=db,
        socket_factory=factory,
    )


async def _start(
    db: sqlite3.Connection,
    factory: MockSocketFactory,
    **kw,
) -> tuple[RelayClient, asyncio.Task, MockRelaySocket]:
    """Create client, start session task, and wait for socket to appear."""
    c = _client(db, factory, **kw)
    task = asyncio.create_task(c._run_session())
    await asyncio.sleep(0)  # give task a chance to call factory & enter __aenter__
    assert factory.socket is not None, "Factory socket not created"
    return c, task, factory.socket


# ─── Auth ─────────────────────────────────────────────────────────────────────


def test_compute_proof_deterministic() -> None:
    p1 = compute_connection_proof("nonce-abc", "secret")
    p2 = compute_connection_proof("nonce-abc", "secret")
    assert p1 == p2


def test_compute_proof_uses_hmac_sha256() -> None:
    nonce, password = "test-nonce", "my-password"
    expected = hmac.new(password.encode(), nonce.encode(), hashlib.sha256).hexdigest()
    assert compute_connection_proof(nonce, password) == expected


def test_wrong_password_gives_different_proof() -> None:
    nonce = "same-nonce"
    assert compute_connection_proof(nonce, "correct") != compute_connection_proof(
        nonce, "wrong"
    )


@pytest.mark.anyio
async def test_auth_success_sends_register(db: sqlite3.Connection) -> None:
    """Client sends a valid register frame with the correct HMAC proof."""
    nonce = "challenge-nonce"
    password = "secret"
    factory = MockSocketFactory(nonce)
    _, task, socket = await _start(db, factory, connection_password=password)

    register = await socket.pull()
    assert register["type"] == "register"
    payload = register["payload"]
    assert payload["bot_id"] == "test-bot"
    assert payload["license_key"] == "test-lic"
    assert payload["connection_password_proof"] == compute_connection_proof(
        nonce, password
    )
    assert "version" in payload

    socket.close()
    await asyncio.gather(task, return_exceptions=True)


@pytest.mark.anyio
async def test_wrong_password_proof_differs_from_correct(
    db: sqlite3.Connection,
) -> None:
    """Bot using the wrong password produces a proof that doesn't match the correct one."""
    nonce = "nonce-xyz"
    factory = MockSocketFactory(nonce)
    _, task, socket = await _start(db, factory, connection_password="wrong-password")

    register = await socket.pull()
    proof_sent = register["payload"]["connection_password_proof"]
    correct_proof = compute_connection_proof(nonce, "correct-password")
    assert proof_sent != correct_proof

    socket.close()
    await asyncio.gather(task, return_exceptions=True)


# ─── RPC dispatch ─────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_dispatches_rpc_request(db: sqlite3.Connection) -> None:
    """Client replies to rpc_request with a matching rpc_response."""
    factory = MockSocketFactory()
    _, task, socket = await _start(db, factory)
    await socket.pull()  # consume register

    req_id = str(uuid.uuid4())
    await socket.push(
        {
            "type": "rpc_request",
            "id": req_id,
            "payload": {"method": "get_active_tickers", "params": {}},
        }
    )

    response = await socket.pull()
    assert response["type"] == "rpc_response"
    assert response["id"] == req_id
    assert "symbols" in response["payload"]["result"]

    socket.close()
    await asyncio.gather(task, return_exceptions=True)


@pytest.mark.anyio
async def test_unknown_method_returns_error(db: sqlite3.Connection) -> None:
    factory = MockSocketFactory()
    _, task, socket = await _start(db, factory)
    await socket.pull()  # register

    req_id = str(uuid.uuid4())
    await socket.push(
        {
            "type": "rpc_request",
            "id": req_id,
            "payload": {"method": "does_not_exist", "params": {}},
        }
    )

    response = await socket.pull()
    assert response["payload"]["error"]["code"] == "UNKNOWN_METHOD"

    socket.close()
    await asyncio.gather(task, return_exceptions=True)


@pytest.mark.anyio
async def test_rpc_response_shares_request_id(db: sqlite3.Connection) -> None:
    """rpc_response must carry the same id as the originating rpc_request."""
    factory = MockSocketFactory()
    _, task, socket = await _start(db, factory)
    await socket.pull()  # register

    req_id = "deterministic-id-42"
    await socket.push(
        {
            "type": "rpc_request",
            "id": req_id,
            "payload": {"method": "get_settings", "params": {}},
        }
    )

    response = await socket.pull()
    assert response["id"] == req_id

    socket.close()
    await asyncio.gather(task, return_exceptions=True)


# ─── Reconnect ────────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_auto_reconnect_after_disconnect(db: sqlite3.Connection) -> None:
    """When the first session drops, run() reconnects and creates a second socket."""
    connection_count = 0

    class CountingFactory:
        def __init__(self) -> None:
            self.sockets: list[MockRelaySocket] = []

        def __call__(self, url: str) -> MockRelaySocket:
            nonlocal connection_count
            connection_count += 1
            sock = MockRelaySocket()
            self.sockets.append(sock)
            return sock

    factory = CountingFactory()
    c = RelayClient(
        url="ws://test",
        bot_id="b",
        license_key="l",
        connection_password="p",
        db=db,
        socket_factory=factory,
    )
    c._backoff = 0.01  # fast retry for test

    task = asyncio.create_task(c.run())

    # Wait for first socket to appear
    for _ in range(50):
        if factory.sockets:
            break
        await asyncio.sleep(0.02)

    assert factory.sockets, "No initial connection made"
    await factory.sockets[0].pull()  # consume register from first session
    factory.sockets[0].close()  # simulate network drop

    # Wait for second connection
    for _ in range(100):
        if connection_count >= 2:
            break
        await asyncio.sleep(0.02)

    assert connection_count >= 2, "Client did not reconnect after disconnect"

    task.cancel()
    await asyncio.gather(task, return_exceptions=True)


# ─── Log stream ───────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_emit_log_after_subscribe(db: sqlite3.Connection) -> None:
    """After subscribe_logs, emit_log sends a log frame."""
    factory = MockSocketFactory()
    client, task, socket = await _start(db, factory)
    await socket.pull()  # register

    # Subscribe to logs
    await socket.push(
        {
            "type": "rpc_request",
            "id": str(uuid.uuid4()),
            "payload": {
                "method": "subscribe_logs",
                "params": {"categories": [], "min_level": "info"},
            },
        }
    )
    sub_resp = await socket.pull()
    assert sub_resp["payload"]["result"]["subscribed"] is True

    # Emit a log
    await client.emit_log("trade", "info", "Position opened", {"symbol": "AAPL"})

    log_frame = await socket.pull()
    assert log_frame["type"] == "log"
    assert log_frame["payload"]["message"] == "Position opened"
    assert log_frame["payload"]["category"] == "trade"

    socket.close()
    await asyncio.gather(task, return_exceptions=True)


@pytest.mark.anyio
async def test_emit_log_filtered_by_level(db: sqlite3.Connection) -> None:
    """Logs below min_level are suppressed."""
    factory = MockSocketFactory()
    client, task, socket = await _start(db, factory)
    await socket.pull()  # register

    await socket.push(
        {
            "type": "rpc_request",
            "id": str(uuid.uuid4()),
            "payload": {
                "method": "subscribe_logs",
                "params": {"categories": [], "min_level": "warning"},
            },
        }
    )
    await socket.pull()  # subscription ack

    # "debug" is below "warning" — must not be forwarded
    await client.emit_log("system", "debug", "Debug message")
    # "warning" should come through
    await client.emit_log("system", "warning", "Warning message")

    frame = await socket.pull()
    assert frame["payload"]["message"] == "Warning message"

    socket.close()
    await asyncio.gather(task, return_exceptions=True)


@pytest.mark.anyio
async def test_emit_log_without_subscription_is_silent(db: sqlite3.Connection) -> None:
    """emit_log before subscribe_logs does nothing (no crash, nothing sent)."""
    factory = MockSocketFactory()
    client, task, socket = await _start(db, factory)
    await socket.pull()  # register

    await client.emit_log("system", "info", "Should be silent")
    assert socket._from_bot.empty()

    socket.close()
    await asyncio.gather(task, return_exceptions=True)


# ─── State update ─────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_emit_state_update(db: sqlite3.Connection) -> None:
    insert_ticker(db, symbol="AAPL")
    factory = MockSocketFactory()
    client, task, socket = await _start(db, factory)
    await socket.pull()  # register

    from bot.control.db import get_all_tickers

    tickers = get_all_tickers(db)
    await client.emit_state_update(tickers)

    frame = await socket.pull()
    assert frame["type"] == "state_update"
    assert frame["payload"]["tickers"][0]["symbol"] == "AAPL"

    socket.close()
    await asyncio.gather(task, return_exceptions=True)


# ─── Localhost-only binding ───────────────────────────────────────────────────


def test_local_api_binds_to_loopback() -> None:
    """The serve() function always uses host=127.0.0.1."""
    import inspect

    from bot.control.local_api import serve

    src = inspect.getsource(serve)
    assert "127.0.0.1" in src, "serve() must bind to 127.0.0.1"
    assert "0.0.0.0" not in src, "serve() must not bind to 0.0.0.0"
