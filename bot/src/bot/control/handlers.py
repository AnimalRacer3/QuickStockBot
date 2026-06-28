"""
RPC handler functions for the bot control service.

Each handler is a plain function accepting (db, params) and returning a dict
that will be serialised into the rpc_response payload. This keeps handlers
testable without any WebSocket machinery.
"""

from __future__ import annotations

import json
import logging
import math
import time
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)

from bot.control import db as dbmod
from bot.control.connection import DbConn

# ─── License / notice constants ───────────────────────────────────────────────

_LICENSE_STATUS_KEY = "_license_cached_status"
_LICENSE_ALLOWED_KEY = "_license_trading_allowed"
_LICENSE_REASON_KEY = "_license_reason"

# As of June 4, 2026 the old $25k PDT / day-trade-counting rules were replaced
# by a risk-based intraday-margin standard.  Brokers may phase the change in
# through October 20, 2027, so the bot defers to the broker's reported state.
_PDT_FRAMEWORK_NOTICE = (
    "NOTICE (June 4, 2026 framework): The $25,000 pattern-day-trader minimum "
    "and day-trade counting were eliminated and replaced by a risk-based "
    "intraday-margin standard. The relevant floor is now the $2,000 margin "
    "minimum (min_account_equity_notice). Buying power is intraday-margin-based. "
    "Because brokers may phase the change in through October 20, 2027, old rules "
    "may still apply until your broker (Alpaca) migrates — the bot defers to "
    "Alpaca's reported restrictions (see Section 6). Not financial advice."
)

_LIVE_MODE_NOTICE = (
    "NOTICE: Live trading is enabled. Paper trading is recommended for new users "
    "and during strategy validation. This software does not provide financial advice. "
    "You trade at your own risk."
)

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
        "exit_mode",
        "trail_off_trigger",
        "daily_target_mode",
    }
)
_BOOL_FIELDS = frozenset(
    {
        "paper_trading",
        "auto_trade",
        "risk_override_enabled",
        "include_unknown_float",
        "require_news",
        "macd_enforce_above_zero",
        "override_risk_per_trade",
        "flatten_on_daily_loss",
        "flatten_on_daily_profit",
        "trailing_stop_enabled",
        "force_close_at_close",
    }
)
_INT_FIELDS = frozenset(
    {
        "max_positions",
        "macd_fast",
        "macd_slow",
        "macd_signal",
        "scanner_refresh_seconds",
        "max_float_shares",
        "active_tickers_n",
        "pattern_candle_lookback",
        "macd_slope_lookback",
    }
)
_FLOAT_FIELDS = frozenset(
    {
        "risk_per_trade_pct",
        "daily_risk_pct",
        "min_score",
        "daily_giveback_pct",
        "pre_open_lead_hours",
        "scan_duration_hours",
        "relative_volume_min",
        "gap_up_min_pct",
        "prior_profit_bias_weight",
        "daily_max_loss_pct",
        "daily_profit_target_pct",
        "trail_off_fraction_per_candle",
        "stop_loss_pct",
        "take_profit_pct",
        "trailing_stop_pct",
    }
)
_LIST_FIELDS = frozenset({"watchlist", "blacklist", "enabled_patterns"})


_DEFAULT_PATTERNS = [
    "bullish_engulfing",
    "hammer",
    "morning_star",
    "bullish_continuation",
]


def _build_settings_response(raw: dict[str, str | None]) -> dict[str, Any]:
    daily_risk = dbmod.coerce_float(raw.get("daily_risk_pct"), 5.0)
    max_pos = dbmod.coerce_int(raw.get("max_positions"), 5)
    # Support both legacy key (risk_override_enabled) and web key (override_risk_per_trade)
    override_on = dbmod.coerce_bool(
        raw.get("override_risk_per_trade") or raw.get("risk_override_enabled"), False
    )
    stored_per_trade = dbmod.coerce_float(raw.get("risk_per_trade_pct"), 1.0)

    if override_on:
        effective_per_trade = stored_per_trade
    else:
        effective_per_trade = daily_risk / max(max_pos, 1)

    goal_post = max(1, math.floor(daily_risk / max(effective_per_trade, 0.001)))

    # daily_max_loss_pct: canonical web key; fall back to daily_risk_pct
    daily_max_loss = dbmod.coerce_float(
        raw.get("daily_max_loss_pct") or raw.get("daily_risk_pct"), daily_risk
    )

    return {
        # Connection / identity
        "bot_id": raw.get("bot_id") or "",
        "relay_url": raw.get("relay_url") or "",
        "license_key": raw.get("license_key") or "",
        "connection_password": raw.get("connection_password"),
        "paper_trading": dbmod.coerce_bool(raw.get("paper_trading"), True),
        "broker": raw.get("broker") or "alpaca",
        "broker_api_key": raw.get("broker_api_key"),
        "broker_api_secret": raw.get("broker_api_secret"),
        # Lists
        "watchlist": dbmod.coerce_list(raw.get("watchlist")),
        "blacklist": dbmod.coerce_list(raw.get("blacklist")),
        # Positions / scoring (legacy keys kept for back-compat)
        "max_positions": max_pos,
        "risk_per_trade_pct": effective_per_trade,
        "daily_risk_pct": daily_risk,
        "risk_override_enabled": override_on,
        "goal_post_trade_count": goal_post,
        "min_score": dbmod.coerce_float(raw.get("min_score"), 60.0),
        "auto_trade": dbmod.coerce_bool(raw.get("auto_trade"), False),
        "log_level": raw.get("log_level") or "info",
        # Daily target mode
        "daily_target_mode": raw.get("daily_target_mode") or "giveback",
        "daily_giveback_pct": dbmod.coerce_float(raw.get("daily_giveback_pct"), 25.0),
        # Scanner
        "pre_open_lead_hours": dbmod.coerce_float(raw.get("pre_open_lead_hours"), 1.0),
        "scan_duration_hours": dbmod.coerce_float(raw.get("scan_duration_hours"), 3.0),
        "scanner_refresh_seconds": dbmod.coerce_int(raw.get("scanner_refresh_seconds"), 60),
        "relative_volume_min": dbmod.coerce_float(raw.get("relative_volume_min"), 2.0),
        "gap_up_min_pct": dbmod.coerce_float(raw.get("gap_up_min_pct"), 5.0),
        "max_float_shares": dbmod.coerce_int(raw.get("max_float_shares"), 20_000_000),
        "include_unknown_float": dbmod.coerce_bool(raw.get("include_unknown_float"), True),
        "require_news": dbmod.coerce_bool(raw.get("require_news"), True),
        "active_tickers_n": dbmod.coerce_int(raw.get("active_tickers_n"), 5),
        "prior_profit_bias_weight": dbmod.coerce_float(
            raw.get("prior_profit_bias_weight"), 0.5
        ),
        # Patterns / MACD
        "enabled_patterns": dbmod.coerce_list(raw.get("enabled_patterns"))
        or _DEFAULT_PATTERNS,
        "pattern_candle_lookback": dbmod.coerce_int(
            raw.get("pattern_candle_lookback"), 5
        ),
        "macd_fast": dbmod.coerce_int(raw.get("macd_fast"), 12),
        "macd_slow": dbmod.coerce_int(raw.get("macd_slow"), 26),
        "macd_signal": dbmod.coerce_int(raw.get("macd_signal"), 9),
        "macd_slope_lookback": dbmod.coerce_int(raw.get("macd_slope_lookback"), 3),
        "macd_enforce_above_zero": dbmod.coerce_bool(
            raw.get("macd_enforce_above_zero"), False
        ),
        # Risk / daily limits
        "daily_max_loss_pct": daily_max_loss,
        "daily_profit_target_pct": dbmod.coerce_float(
            raw.get("daily_profit_target_pct"), 7.0
        ),
        "override_risk_per_trade": override_on,
        "flatten_on_daily_loss": dbmod.coerce_bool(
            raw.get("flatten_on_daily_loss"), True
        ),
        "flatten_on_daily_profit": dbmod.coerce_bool(
            raw.get("flatten_on_daily_profit"), False
        ),
        # Exits
        "exit_mode": raw.get("exit_mode") or "trail_off",
        "trail_off_trigger": raw.get("trail_off_trigger") or "candle_pattern",
        "trail_off_fraction_per_candle": dbmod.coerce_float(
            raw.get("trail_off_fraction_per_candle"), 0.25
        ),
        "stop_loss_pct": dbmod.coerce_float(raw.get("stop_loss_pct"), 2.0),
        "take_profit_pct": dbmod.coerce_float(raw.get("take_profit_pct"), 4.0),
        "trailing_stop_enabled": dbmod.coerce_bool(
            raw.get("trailing_stop_enabled"), False
        ),
        "trailing_stop_pct": dbmod.coerce_float(raw.get("trailing_stop_pct"), 1.0)
        if raw.get("trailing_stop_pct")
        else None,
        "force_close_at_close": dbmod.coerce_bool(
            raw.get("force_close_at_close"), True
        ),
    }


# ─── Handlers ─────────────────────────────────────────────────────────────────


def _build_notices(db: DbConn, account: dict | None) -> list[dict]:
    """Compile runtime notices surfaced to the dashboard."""
    notices: list[dict] = []

    # ── License notice ────────────────────────────────────────────────────
    lic_rows = {
        r["key"]: r["value"]
        for r in db.execute(
            "SELECT key, value FROM settings WHERE key IN (%s, %s, %s)",
            (_LICENSE_STATUS_KEY, _LICENSE_ALLOWED_KEY, _LICENSE_REASON_KEY),
        ).fetchall()
    }
    lic_status = lic_rows.get(_LICENSE_STATUS_KEY, "unknown")
    lic_allowed_str = lic_rows.get(_LICENSE_ALLOWED_KEY, "false") or "false"
    lic_trading_allowed = lic_allowed_str.lower() in ("true", "1")
    lic_reason = lic_rows.get(_LICENSE_REASON_KEY, "")

    if lic_status != "active":
        notices.append(
            {
                "type": "license",
                "severity": "warning" if lic_trading_allowed else "error",
                "trading_allowed": lic_trading_allowed,
                "message": lic_reason or f"license status: {lic_status}",
            }
        )

    # ── Live-mode notice ──────────────────────────────────────────────────
    paper_row = db.execute(
        "SELECT value FROM settings WHERE key = 'paper_trading'"
    ).fetchone()
    paper_val = (paper_row["value"] if paper_row else "true") or "true"
    is_live = paper_val.lower() not in ("true", "1")

    if is_live:
        notices.append(
            {
                "type": "live_mode",
                "severity": "warning",
                "message": _LIVE_MODE_NOTICE,
            }
        )

    # ── Account equity / PDT framework notice ─────────────────────────────
    notices.append(
        {
            "type": "account_equity",
            "severity": "info",
            "message": _PDT_FRAMEWORK_NOTICE,
            "pdt_framework": {
                "effective_date": "2026-06-04",
                "broker_migration_deadline": "2027-10-20",
                "min_account_equity_notice": 2000.0,
                "old_pdt_rule_eliminated": True,
                "broker_may_still_use_old_rules": True,
            },
        }
    )

    if account:
        is_pdt_restricted = bool(account.get("is_pdt_restricted", False))
        day_trade_count = account.get("day_trade_count", 0)
        if is_pdt_restricted:
            notices.append(
                {
                    "type": "pdt_restricted",
                    "severity": "warning",
                    "day_trade_count": day_trade_count,
                    "message": (
                        "PDT flag active on your Alpaca account — new entries blocked. "
                        "This may reflect old rules still in effect at your broker "
                        "pending their migration to the June 4, 2026 framework."
                    ),
                }
            )

    return notices


def handle_get_state(db: DbConn, params: dict) -> dict:
    tickers = dbmod.get_all_tickers(db)

    # Account snapshot cached in settings as JSON
    raw_acct = db.execute(
        "SELECT value FROM settings WHERE key = '_account_snapshot'"
    ).fetchone()
    account = None
    if raw_acct and raw_acct["value"]:
        try:
            account = json.loads(raw_acct["value"])
        except Exception:
            pass

    notices = _build_notices(db, account)
    return {"tickers": tickers, "account": account, "notices": notices}


def handle_get_active_tickers(db: DbConn, params: dict) -> dict:
    rows = db.execute("SELECT symbol FROM active_tickers ORDER BY symbol").fetchall()
    return {"symbols": [r[0] for r in rows]}


def handle_get_ticker_detail(db: DbConn, params: dict) -> dict:
    symbol = params.get("symbol", "")
    if not symbol:
        raise ValueError("symbol parameter is required")
    ticker = dbmod.get_ticker(db, symbol)
    if ticker is None:
        raise ValueError(f"Ticker not found: {symbol}")
    return ticker


def handle_get_settings(db: DbConn, params: dict) -> dict:
    raw = dbmod.get_all_settings_raw(db)
    return _build_settings_response(raw)


def handle_update_settings(db: DbConn, params: dict) -> dict:
    patch: dict = dict(params.get("patch") or {})  # copy; we may pop keys
    if not patch:
        return handle_get_settings(db, {})

    # ── Live-mode confirmation gate ──────────────────────────────────────
    # Popped before the write loop so it is never persisted.
    live_confirmed = patch.pop("live_mode_confirmed", None)
    if "paper_trading" in patch and not patch["paper_trading"]:
        if not live_confirmed:
            raise ValueError(
                "live_mode_confirmation_required: enabling live trading requires "
                "live_mode_confirmed=true. Paper trading is recommended for new "
                "users and during strategy validation. Not financial advice."
            )

    raw = dbmod.get_all_settings_raw(db)

    # Determine override state AFTER applying the patch (supports both key names)
    new_override = patch.get(
        "override_risk_per_trade",
        patch.get(
            "risk_override_enabled",
            dbmod.coerce_bool(
                raw.get("override_risk_per_trade") or raw.get("risk_override_enabled"),
                False,
            ),
        ),
    )
    if isinstance(new_override, str):
        new_override = new_override.lower() in ("true", "1")

    # Support both daily_max_loss_pct (web) and daily_risk_pct (legacy)
    new_daily = abs(
        float(
            patch.get(
                "daily_max_loss_pct",
                patch.get(
                    "daily_risk_pct",
                    dbmod.coerce_float(
                        raw.get("daily_max_loss_pct") or raw.get("daily_risk_pct"), 5.0
                    ),
                ),
            )
        )
    )

    # Enforce override rules on risk_per_trade_pct
    if "risk_per_trade_pct" in patch:
        if new_override:
            if patch["risk_per_trade_pct"] >= new_daily:
                raise ValueError(
                    f"risk_per_trade_pct ({patch['risk_per_trade_pct']}) must be "
                    f"strictly less than daily_max_loss_pct ({new_daily}) when "
                    "override_risk_per_trade is true"
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
            "INSERT INTO settings (key, value, updated_at) VALUES (%s, %s, %s)"
            " ON CONFLICT (key) DO UPDATE SET"
            " value = EXCLUDED.value, updated_at = EXCLUDED.updated_at",
            (key, serialized, now),
        )

    db.commit()
    return handle_get_settings(db, {})


def handle_get_lists(db: DbConn, params: dict) -> dict:
    return {
        "watchlist": dbmod.get_list_symbols(db, "watchlist"),
        "blacklist": dbmod.get_list_symbols(db, "blacklist"),
    }


def handle_update_lists(db: DbConn, params: dict) -> dict:
    if "watchlist" in params:
        dbmod.replace_list(db, "watchlist", params["watchlist"])
    if "blacklist" in params:
        dbmod.replace_list(db, "blacklist", params["blacklist"])
    return handle_get_lists(db, {})


def handle_get_trade_history(db: DbConn, params: dict) -> dict:
    limit = min(int(params.get("limit", 100)), 500)
    offset = int(params.get("offset", 0))
    trades, total = dbmod.get_trade_history(db, limit, offset)
    return {"trades": trades, "total": total}


def handle_get_order_detail(db: DbConn, params: dict) -> dict:
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


def handle_get_daily_pl(db: DbConn, params: dict) -> dict:
    start = params.get("start")
    end = params.get("end")
    if not start or not end:
        raise ValueError("start and end parameters are required")
    return {"days": dbmod.get_daily_pl(db, start, end)}


def handle_trigger_scan(db: DbConn, params: dict) -> dict:
    """Queue a scan cycle. The background scan loop picks this up within seconds."""
    now = int(time.time())
    db.execute(
        "INSERT INTO settings (key, value, updated_at) VALUES (%s, %s, %s)"
        " ON CONFLICT (key) DO UPDATE SET"
        " value = EXCLUDED.value, updated_at = EXCLUDED.updated_at",
        ("_scan_requested", "1", now),
    )
    db.commit()
    logger.info("Scan trigger requested via RPC")
    return {"queued": True}


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
    "trigger_scan": handle_trigger_scan,
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
