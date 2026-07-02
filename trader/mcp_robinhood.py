"""Robinhood brokerage layer, accessed as an MCP client.

The bot never talks to Robinhood directly. It connects, as a programmatic
MCP client (the official `mcp` Python package), to whatever Robinhood MCP
server is already configured for Claude Code on this machine, reusing its
stored auth. Tool *names* are never hardcoded: at startup we list the
server's tools and fuzzy-map them to the roles the bot needs
(get_account, get_positions, get_quote, place_order, cancel_order,
order_status). If auth is rejected or a required role can't be found among
the server's tools, we fail loudly rather than guessing.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
import threading
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger("trader.mcp")

REQUIRED_ROLES = (
    "get_account",
    "get_positions",
    "get_quote",
    "place_order",
    "cancel_order",
    "order_status",
)

# Keyword sets used to fuzzy-match a server's advertised tool name/description
# to the role the bot needs. Order matters: more specific roles are matched
# first so a generic "order" tool doesn't get grabbed by the wrong role.
_ROLE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "place_order": ("place_order", "submit_order", "create_order", "buy_stock", "sell_stock", "place_trade", "execute_order"),
    "cancel_order": ("cancel_order", "cancel_trade", "cancel"),
    "order_status": ("order_status", "get_order", "check_order", "order_info", "order_details"),
    "get_quote": ("get_quote", "quote", "last_price", "market_price", "current_price"),
    "get_positions": ("get_positions", "positions", "holdings", "portfolio"),
    "get_account": ("get_account", "account_info", "account_balance", "buying_power", "equity", "account"),
}
_ROLE_PRIORITY = ("place_order", "cancel_order", "order_status", "get_quote", "get_positions", "get_account")


class MCPConfigError(Exception):
    """Robinhood MCP server could not be found, connected to, or role-mapped."""


@dataclass(frozen=True)
class MCPServerSpec:
    name: str
    command: str | None = None
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    url: str | None = None
    headers: dict[str, str] = field(default_factory=dict)
    transport: str = "stdio"  # "stdio" | "sse" | "http" ("http" = MCP Streamable HTTP)


def _load_mcp_servers_from_file(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data.get("mcpServers", {})


def _spec_from_raw(name: str, raw: dict[str, Any]) -> MCPServerSpec:
    if "url" in raw:
        # Claude Code's config uses "type" for remote servers: "sse" (legacy) or
        # "http" (MCP Streamable HTTP, the modern default for most hosted servers).
        transport = raw.get("transport") or raw.get("type") or "http"
        return MCPServerSpec(name=name, url=raw["url"], headers=dict(raw.get("headers", {})), transport=transport)
    return MCPServerSpec(
        name=name,
        command=raw.get("command"),
        args=list(raw.get("args", [])),
        env=dict(raw.get("env", {})),
        transport="stdio",
    )


def _describe_exception(exc: BaseException) -> str:
    """Unwrap ExceptionGroup/TaskGroup errors into a readable, non-vague message.

    anyio TaskGroups (used by the mcp SDK's transports) wrap the real failure
    in a bare `ExceptionGroup`, whose default `str()` is the unhelpful
    "unhandled errors in a TaskGroup (N sub-exception(s))" -- this recurses
    into `.exceptions` to surface what actually failed (e.g. an HTTP 401,
    a TLS error, a DNS failure).
    """
    sub_exceptions = getattr(exc, "exceptions", None)
    if not sub_exceptions:
        return f"{type(exc).__name__}: {exc}"
    parts = [_describe_exception(sub) for sub in sub_exceptions]
    return f"{type(exc).__name__}({'; '.join(parts)})"


def _looks_like_robinhood(name: str, raw: dict[str, Any]) -> bool:
    haystack = json.dumps(raw).lower() + name.lower()
    return "robinhood" in haystack


def discover_robinhood_mcp_server(search_dirs: list[Path] | None = None) -> MCPServerSpec:
    """Find the Robinhood MCP server already configured for Claude Code.

    Checks, in order: `.mcp.json` in the given directories (project scope),
    then `~/.claude.json` (user scope), then `claude mcp list` as a last
    resort for servers registered outside those files.
    """
    dirs = search_dirs or [Path.cwd()]
    candidates: dict[str, dict[str, Any]] = {}

    for d in dirs:
        candidates.update(_load_mcp_servers_from_file(d / ".mcp.json"))

    home_claude_json = Path.home() / ".claude.json"
    if home_claude_json.exists():
        try:
            data = json.loads(home_claude_json.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
        candidates.update(data.get("mcpServers", {}))
        for project in data.get("projects", {}).values():
            candidates.update(project.get("mcpServers", {}))

    robinhood_entries = {n: r for n, r in candidates.items() if _looks_like_robinhood(n, r)}
    if len(robinhood_entries) == 1:
        name, raw = next(iter(robinhood_entries.items()))
        return _spec_from_raw(name, raw)
    if len(robinhood_entries) > 1:
        name, raw = next(iter(robinhood_entries.items()))
        logger.warning("Multiple candidate Robinhood MCP servers found in config; using %r", name)
        return _spec_from_raw(name, raw)

    # Last resort: ask the `claude` CLI directly.
    try:
        result = subprocess.run(
            ["claude", "mcp", "list"], capture_output=True, text=True, timeout=15, check=False
        )
        for line in result.stdout.splitlines():
            if "robinhood" in line.lower():
                name = line.split(":", 1)[0].strip()
                detail = subprocess.run(
                    ["claude", "mcp", "get", name], capture_output=True, text=True, timeout=15, check=False
                )
                spec = _parse_claude_mcp_get(name, detail.stdout)
                if spec:
                    return spec
    except (OSError, subprocess.SubprocessError) as exc:
        logger.debug("`claude mcp list` unavailable: %s", exc)

    raise MCPConfigError(
        "Could not find a Robinhood MCP server in .mcp.json, ~/.claude.json, or "
        "`claude mcp list`. Configure it for Claude Code first, then rerun."
    )


def _parse_claude_mcp_get(name: str, output: str) -> MCPServerSpec | None:
    command = None
    args: list[str] = []
    url = None
    for line in output.splitlines():
        line = line.strip()
        if line.lower().startswith("command:"):
            command = line.split(":", 1)[1].strip()
        elif line.lower().startswith("args:"):
            args = line.split(":", 1)[1].strip().split()
        elif line.lower().startswith("url:"):
            url = line.split(":", 1)[1].strip()
    if url:
        return MCPServerSpec(name=name, url=url, transport="sse")
    if command:
        return MCPServerSpec(name=name, command=command, args=args, transport="stdio")
    return None


class RobinhoodMCPClient:
    """Synchronous-facing wrapper around an async MCP ClientSession.

    Runs a dedicated background asyncio event loop thread so the rest of
    the (synchronous) trading engine can call `get_account()`,
    `place_order()`, etc. as plain blocking calls.
    """

    def __init__(self, spec: MCPServerSpec):
        self.spec = spec
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._session: Any = None
        self._exit_stack: AsyncExitStack | None = None
        self.role_map: dict[str, str] = {}
        self._ready = threading.Event()
        self._error: Exception | None = None

    # -- lifecycle ---------------------------------------------------------

    def connect(self, timeout: float = 30.0) -> None:
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="mcp-robinhood")
        self._thread.start()
        if not self._ready.wait(timeout):
            raise MCPConfigError(f"Timed out connecting to Robinhood MCP server {self.spec.name!r}")
        if self._error:
            raise self._error

    def close(self) -> None:
        if self._loop and self._exit_stack:
            fut = asyncio.run_coroutine_threadsafe(self._exit_stack.aclose(), self._loop)
            try:
                fut.result(timeout=10)
            except Exception:  # noqa: BLE001 - best-effort shutdown
                pass
        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread:
            self._thread.join(timeout=5)

    def _run_loop(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._connect_async())
            self._ready.set()
            self._loop.run_forever()
        except Exception as exc:  # noqa: BLE001
            # Wrap anything that isn't already a clear MCPConfigError so a raw
            # anyio ExceptionGroup ("unhandled errors in a TaskGroup (1
            # sub-exception)") never reaches the caller without its real cause.
            if isinstance(exc, MCPConfigError):
                self._error = exc
            else:
                self._error = MCPConfigError(
                    f"Failed to connect to Robinhood MCP server {self.spec.name!r} "
                    f"({self.spec.transport} {self.spec.url or self.spec.command}): {_describe_exception(exc)}"
                )
            self._ready.set()

    async def _connect_async(self) -> None:
        from mcp import ClientSession
        from mcp.client.stdio import StdioServerParameters, stdio_client

        self._exit_stack = AsyncExitStack()

        if self.spec.transport == "stdio":
            if not self.spec.command:
                raise MCPConfigError(f"MCP server {self.spec.name!r} has no command configured")
            params = StdioServerParameters(
                command=self.spec.command,
                args=self.spec.args,
                env={**os.environ, **self.spec.env},
            )
            read, write = await self._exit_stack.enter_async_context(stdio_client(params))
        elif self.spec.transport == "sse":
            from mcp.client.sse import sse_client

            if not self.spec.url:
                raise MCPConfigError(f"MCP server {self.spec.name!r} has no url configured")
            read, write = await self._exit_stack.enter_async_context(
                sse_client(self.spec.url, headers=self.spec.headers or None)
            )
        elif self.spec.transport == "http":
            from mcp.client.streamable_http import streamablehttp_client

            if not self.spec.url:
                raise MCPConfigError(f"MCP server {self.spec.name!r} has no url configured")
            # Streamable HTTP yields a 3-tuple (read, write, get_session_id) -- unlike
            # stdio/SSE's 2-tuple -- which is the bug that caused a raw TaskGroup
            # failure here before: unpacking it as (read, write) desyncs the streams.
            read, write, _get_session_id = await self._exit_stack.enter_async_context(
                streamablehttp_client(self.spec.url, headers=self.spec.headers or None)
            )
        else:
            raise MCPConfigError(f"Unsupported MCP transport {self.spec.transport!r}")

        session = await self._exit_stack.enter_async_context(ClientSession(read, write))
        try:
            await session.initialize()
        except Exception as exc:  # noqa: BLE001
            raise MCPConfigError(
                f"Robinhood MCP server {self.spec.name!r} rejected initialization "
                f"(likely an auth failure): {_describe_exception(exc)}"
            ) from exc

        self._session = session

        tools_result = await session.list_tools()
        self.role_map = _map_tools_to_roles(tools_result.tools)
        missing = [r for r in REQUIRED_ROLES if r not in self.role_map]
        if missing:
            available = [t.name for t in tools_result.tools]
            raise MCPConfigError(
                f"Robinhood MCP server {self.spec.name!r} is missing required role(s) "
                f"{missing}; available tools: {available}"
            )
        logger.info("Robinhood MCP role map: %s", self.role_map)

    # -- sync call bridge ----------------------------------------------------

    def _call_tool_sync(self, role: str, arguments: dict[str, Any], timeout: float = 20.0) -> dict[str, Any]:
        if self._loop is None or self._session is None:
            raise MCPConfigError("Robinhood MCP client is not connected")
        tool_name = self.role_map[role]
        fut = asyncio.run_coroutine_threadsafe(
            self._session.call_tool(tool_name, arguments), self._loop
        )
        result = fut.result(timeout=timeout)
        if getattr(result, "isError", False):
            raise MCPConfigError(f"Robinhood MCP tool {tool_name!r} (role={role}) returned an error: {result}")
        return _extract_result_payload(result)

    # -- role-mapped operations ------------------------------------------

    def get_account(self) -> dict[str, Any]:
        return self._call_tool_sync("get_account", {})

    def get_positions(self) -> list[dict[str, Any]]:
        payload = self._call_tool_sync("get_positions", {})
        if isinstance(payload, list):
            return payload
        return payload.get("positions", []) if isinstance(payload, dict) else []

    def get_quote(self, symbol: str) -> dict[str, Any]:
        return self._call_tool_sync("get_quote", {"symbol": symbol})

    def place_order(
        self, symbol: str, side: str, qty: float, order_type: str = "market", limit_price: float | None = None
    ) -> dict[str, Any]:
        args: dict[str, Any] = {"symbol": symbol, "side": side, "quantity": qty, "type": order_type}
        if limit_price is not None:
            args["limit_price"] = limit_price
        return self._call_tool_sync("place_order", args)

    def cancel_order(self, order_id: str) -> dict[str, Any]:
        return self._call_tool_sync("cancel_order", {"order_id": order_id})

    def order_status(self, order_id: str) -> dict[str, Any]:
        return self._call_tool_sync("order_status", {"order_id": order_id})


def _map_tools_to_roles(tools: list[Any]) -> dict[str, str]:
    scores: list[tuple[float, str, str]] = []  # (score, role, tool_name)
    for tool in tools:
        haystack = f"{tool.name} {tool.description or ''}".lower()
        for role in _ROLE_PRIORITY:
            score = sum(1 for kw in _ROLE_KEYWORDS[role] if kw in haystack)
            if tool.name.lower() == role:
                score += 10
            if score > 0:
                scores.append((score, role, tool.name))

    scores.sort(key=lambda t: t[0], reverse=True)
    role_map: dict[str, str] = {}
    used_tools: set[str] = set()
    for score, role, tool_name in scores:
        if role in role_map or tool_name in used_tools:
            continue
        role_map[role] = tool_name
        used_tools.add(tool_name)
    return role_map


def _extract_result_payload(result: Any) -> Any:
    """MCP tool results carry a list of content blocks; pull structured JSON if present."""
    if hasattr(result, "structuredContent") and result.structuredContent is not None:
        return result.structuredContent
    for block in getattr(result, "content", []):
        text = getattr(block, "text", None)
        if text:
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return {"text": text}
    return {}
