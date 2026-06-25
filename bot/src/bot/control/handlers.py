"""
RPC handler functions for the bot control service.

Each handler is a plain function accepting (db, params) and returning a dict
that will be serialised into the rpc_response payload. This keeps handlers
testable without any WebSocket machinery.
"""

from __future__ import annotations

import math
import sqlite3
import time
from collections.abc import Callable
from typing import Any

from bot.control import db as dbmod

# ─── Settings helpers ─────────────────────────────────────────────────────────

# Fields whose values must never be set by update_settings
_READ_ONLY = frozenset({"goal_post_trade_count"})

# Fields accepted verbatim as strings
_STR_FIELDS = frozenset(
    {
        "bot_id",
        "relay_url",
        "license_key",
        "connection_password",
        "broker",
        "broker_api_key",
        "broker_api_secret",
        "log_level",
    }
)
_BOOL_FIELDS = frozenset({"paper_trading", "auto_trade", "risk_override_enabled"})
_INT_FIELDS = frozenset({"max_positions", "macd_fast", "macd_slow", "macd_signal"})
_FLOAT_FIELDS = frozenset({"risk_per_trade_pct", "daily_risk_pct", "min_score"})
_LIST_FIELDS = frozenset({"watchlist", "blacklist"})


def _build_settings_response(raw: dict[str, str | None]) -> dict[str, Any]:
    daily_risk = dbmod.coerce_float(raw.get("daily_risk_pct"), 5.0)
    max_pos = dbmod.coerce_int(raw.get("max_positions"), 5)
    override_on = dbmod.coerce_bool(raw.get("risk_override_enabled"), False)
    stored_per_trade = dbmod.coerce_float(raw.get("risk_per_trade_pct"), 1.0)

    if override_on:
        effective_per_trade = stored_per_trade
    else:
        # Locked: always computed from daily / max_positions
        effective_per_trade = daily_risk / max(max_pos, 1)

    goal_post = max(1, math.floor(daily_risk / effective_per_trade))

    return {
        "bot_id": raw.get("bot_id") or "",
        "relay_url": raw.get("relay_url") or "",
        "license_key": raw.get("license_key") or "",
        "connection_password": raw.get("connection_password"),
        "paper_trading": dbmod.coerce_bool(raw.get("paper_trading"), True),
        "broker": raw.get("broker") or "alpaca",
        "broker_api_key": raw.get("broker_api_key"),
        "broker_api_secret": raw.get("broker_api_secret"),
        "watchlist": dbmod.coerce_list(raw.get("watchlist")),
        "blacklist": dbmod.coerce_list(raw.get("blacklist")),
        "max_positions": max_pos,
        "risk_per_trade_pct": effective_per_trade,
        "daily_risk_pct": daily_risk,
        "risk_override_enabled": override_on,
        "goal_post_trade_count": goal_post,
        "min_score": dbmod.coerce_float(raw.get("min_score"), 60.0),
        "auto_trade": dbmod.coerce_bool(raw.get("auto_trade"), False),
        "macd_fast": dbmod.coerce_int(raw.get("macd_fast"), 12),
        "macd_slow": dbmod.coerce_int(raw.get("macd_slow"), 26),
        "macd_signal": dbmod.coerce_int(raw.get("macd_signal"), 9),
        "log_level": raw.get("log_level") or "info",
    }


# ─── Handlers ─────────────────────────────────────────────────────────────────


def handle_get_state(db: sqlite3.Connection, params: dict) -> dict:
    tickers = dbmod.get_all_tickers(db)

    # Account snapshot cached in settings as JSON
    raw_acct = db.execute(
        "SELECT value FROM settings WHERE key = '_account_snapshot'"
    ).fetchone()
    account = None
    if raw_acct and raw_acct[0]:
        import json

        try:
            account = json.loads(raw_acct[0])
        except Exception:
            pass

    return {"tickers": tickers, "account": account}


def handle_get_active_tickers(db: sqlite3.Connection, params: dict) -> dict:
    rows = db.execute("SELECT symbol FROM active_tickers ORDER BY symbol").fetchall()
    return {"symbols": [r[0] for r in rows]}


def handle_get_ticker_detail(db: sqlite3.Connection, params: dict) -> dict:
    symbol = params.get("symbol", "")
    if not symbol:
        raise ValueError("symbol parameter is required")
    ticker = dbmod.get_ticker(db, symbol)
    if ticker is None:
        raise ValueError(f"Ticker not found: {symbol}")
    return ticker


def handle_get_settings(db: sqlite3.Connection, params: dict) -> dict:
    raw = dbmod.get_all_settings_raw(db)
    return _build_settings_response(raw)


def handle_update_settings(db: sqlite3.Connection, params: dict) -> dict:
    patch: dict = params.get("patch") or {}
    if not patch:
        return handle_get_settings(db, {})

    raw = dbmod.get_all_settings_raw(db)

    # Determine override state AFTER applying the patch (so the patch can
    # change risk_override_enabled in the same call).
    new_override = patch.get(
        "risk_override_enabled",
        dbmod.coerce_bool(raw.get("risk_override_enabled"), False),
    )
    if isinstance(new_override, str):
        new_override = new_override.lower() in ("true", "1")

    new_daily = patch.get(
        "daily_risk_pct",
        dbmod.coerce_float(raw.get("daily_risk_pct"), 5.0),
    )

    # Enforce override rules on risk_per_trade_pct
    if "risk_per_trade_pct" in patch:
        if new_override:
            if patch["risk_per_trade_pct"] >= new_daily:
                raise ValueError(
                    f"risk_per_trade_pct ({patch['risk_per_trade_pct']}) must be "
                    f"strictly less than daily_risk_pct ({new_daily}) when "
                    "risk_override_enabled is true"
                )
        else:
            # Override is off — silently discard the per-trade value.
            del patch["risk_per_trade_pct"]

    now = int(time.time())
    for key, val in patch.items():
        if key in _READ_ONLY:
            continue
        if key in _LIST_FIELDS:
            serialized = dbmod.serialize_value(val)
        elif key in _BOOL_FIELDS:
            serialized = "true" if val else "false"
        elif key in _INT_FIELDS:
            serialized = str(int(val))
        elif key in _FLOAT_FIELDS:
            serialized = str(float(val))
        else:
            serialized = str(val) if val is not None else ""
        db.execute(
            "INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, ?)",
            (key, serialized, now),
        )

    db.commit()
    return handle_get_settings(db, {})


def handle_get_lists(db: sqlite3.Connection, params: dict) -> dict:
    return {
        "watchlist": dbmod.get_list_symbols(db, "watchlist"),
        "blacklist": dbmod.get_list_symbols(db, "blacklist"),
    }


def handle_update_lists(db: sqlite3.Connection, params: dict) -> dict:
    if "watchlist" in params:
        dbmod.replace_list(db, "watchlist", params["watchlist"])
    if "blacklist" in params:
        dbmod.replace_list(db, "blacklist", params["blacklist"])
    return handle_get_lists(db, {})


def handle_get_trade_history(db: sqlite3.Connection, params: dict) -> dict:
    limit = min(int(params.get("limit", 100)), 500)
    offset = int(params.get("offset", 0))
    trades, total = dbmod.get_trade_history(db, limit, offset)
    return {"trades": trades, "total": total}


def handle_get_order_detail(db: sqlite3.Connection, params: dict) -> dict:
    order_id = params.get("order_id", "")
    if not order_id:
        raise ValueError("order_id parameter is required")
    order = dbmod.get_order(db, order_id)
    if order is None:
        raise ValueError(f"Order not found: {order_id}")
    return order


def handle_subscribe_logs(
    db: sqlite3.Connection,
    params: dict,
    on_subscribe: Callable[[dict], None] | None = None,
) -> dict:
    if on_subscribe is not None:
        on_subscribe(
            {
                "categories": params.get("categories", []),
                "min_level": params.get("min_level", "info"),
            }
        )
    return {"subscribed": True}


def handle_get_daily_pl(db: sqlite3.Connection, params: dict) -> dict:
    start = params.get("start")
    end = params.get("end")
    if not start or not end:
        raise ValueError("start and end parameters are required")
    return {"days": dbmod.get_daily_pl(db, start, end)}


# ─── Dispatcher ───────────────────────────────────────────────────────────────

_HANDLERS: dict[str, Callable] = {
    "get_state": handle_get_state,
    "get_active_tickers": handle_get_active_tickers,
    "get_ticker_detail": handle_get_ticker_detail,
    "get_settings": handle_get_settings,
    "update_settings": handle_update_settings,
    "get_lists": handle_get_lists,
    "update_lists": handle_update_lists,
    "get_trade_history": handle_get_trade_history,
    "get_order_detail": handle_get_order_detail,
    "subscribe_logs": handle_subscribe_logs,
    "get_daily_pl": handle_get_daily_pl,
}


def dispatch(
    method: str,
    db: sqlite3.Connection,
    params: dict,
    on_subscribe: Callable[[dict], None] | None = None,
) -> dict:
    """Route *method* to its handler and return the result dict."""
    if method not in _HANDLERS:
        raise KeyError(method)
    handler = _HANDLERS[method]
    if method == "subscribe_logs":
        return handler(db, params, on_subscribe)
    return handler(db, params)
