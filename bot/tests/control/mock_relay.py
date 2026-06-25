"""
MockRelaySocket — in-process simulation of a relay WebSocket connection.

``MockRelaySocket`` implements the same async context-manager / iterator
interface that ``websockets.connect()`` yields, so it can be injected
directly into ``RelayClient`` as the *socket_factory*.
"""

from __future__ import annotations

import asyncio
import json

_CLOSED = object()  # sentinel


class MockRelaySocket:
    """
    Simulates one relay ↔ bot WebSocket session.

    The mock automatically pushes an ``auth_challenge`` frame when entered so
    the bot's authentication path runs without extra test boilerplate.
    """

    def __init__(self, nonce: str = "test-nonce") -> None:
        self.nonce = nonce
        # Messages the relay sends to the bot (bot calls recv/iteration)
        self._to_bot: asyncio.Queue = asyncio.Queue()
        # Messages the bot sends to the relay (test calls pull)
        self._from_bot: asyncio.Queue = asyncio.Queue()
        self._closed = False

    # ── Async context-manager ───────────────────────────────────────────────

    async def __aenter__(self) -> "MockRelaySocket":
        # Push the auth_challenge so the bot sees it on its first recv()
        await self._to_bot.put(
            json.dumps(
                {
                    "type": "auth_challenge",
                    "id": "challenge-001",
                    "payload": {"nonce": self.nonce},
                }
            )
        )
        return self

    async def __aexit__(self, *args: object) -> None:
        self.close()

    # ── WebSocket-compatible interface ──────────────────────────────────────

    async def recv(self) -> str:
        item = await self._to_bot.get()
        if item is _CLOSED:
            raise ConnectionError("MockRelaySocket closed")
        return item  # type: ignore[return-value]

    async def send(self, data: str) -> None:
        await self._from_bot.put(data)

    def __aiter__(self) -> "MockRelaySocket":
        return self

    async def __anext__(self) -> str:
        if self._closed and self._to_bot.empty():
            raise StopAsyncIteration
        item = await self._to_bot.get()
        if item is _CLOSED:
            raise StopAsyncIteration
        return item  # type: ignore[return-value]

    # ── Test helpers ────────────────────────────────────────────────────────

    async def push(self, msg: dict) -> None:
        """Inject a message that the bot will receive next."""
        await self._to_bot.put(json.dumps(msg))

    async def pull(self, timeout: float = 3.0) -> dict:
        """Collect the next message the bot sent to the relay."""
        raw = await asyncio.wait_for(self._from_bot.get(), timeout=timeout)
        return json.loads(raw)

    def close(self) -> None:
        """Signal end-of-stream to the bot's dispatch loop."""
        if not self._closed:
            self._closed = True
            self._to_bot.put_nowait(_CLOSED)


class MockSocketFactory:
    """
    A callable factory that creates ``MockRelaySocket`` instances.

    Use as ``socket_factory`` when constructing ``RelayClient`` in tests:

        factory = MockSocketFactory()
        client = RelayClient(..., socket_factory=factory)
        # factory.socket is the most recently created socket
    """

    def __init__(self, nonce: str = "test-nonce") -> None:
        self._nonce = nonce
        self.socket: MockRelaySocket | None = None
        self.connection_count = 0

    def __call__(self, url: str) -> MockRelaySocket:
        self.socket = MockRelaySocket(self._nonce)
        self.connection_count += 1
        return self.socket
