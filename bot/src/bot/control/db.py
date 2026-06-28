"""
Lightweight database access for the control service.

All functions accept a DbConn so the caller controls connection lifecycle.
In production DbConn wraps a psycopg2 connection (DATABASE_URL); in tests
it wraps an in-memory sqlite3 connection.  All SQL uses %s placeholders and
PostgreSQL-compatible ON CONFLICT syntax.
"""

from __future__ import annotations

import datetime
import json
import time

from bot.control.connection import DbConn

# ─── Utilities ────────────────────────────────────────────────────────────────


def ts_to_iso(ts: int | None) -> str | None:
    if ts is None:
        return None
    return datetime.datetime.utcfromtimestamp(ts).strftime("%Y-%m-%dT%H:%M:%SZ")


# ─── Settings ─────────────────────────────────────────────────────────────────

SETTING_DEFAULTS: dict[str, str | None] = {
    # Connection / auth
    "bot_id": "",
    "relay_url": "",
    "license_key": "",
    "connection_password": None,
    "paper_trading": "true",
    "broker": "alpaca",
    "broker_api_key": None,
    "broker_api_secret": None,
    # Positions / scoring
    "max_positions": "5",
    "risk_per_trade_pct": "1.0",
    "daily_risk_pct": "5.0",
    "risk_override_enabled": "false",
    "min_score": "60.0",
    "auto_trade": "false",
    "log_level": "info",
    # Daily target mode
    "daily_target_mode": "giveback",
    "daily_giveback_pct": "25.0",
    # Scanner
    "pre_open_lead_hours": "1.0",
    "scan_duration_hours": "3.0",
    "scanner_refresh_seconds": "60",
    "relative_volume_min": "2.0",
    "gap_up_min_pct": "5.0",
    "max_float_shares": "20000000",
    "include_unknown_float": "true",
    "require_news": "true",
    "active_tickers_n": "5",
    "prior_profit_bias_weight": "0.5",
    # Patterns / MACD
    "enabled_patterns": '["bullish_engulfing","hammer","morning_star","bullish_continuation"]',
    "pattern_candle_lookback": "5",
    "macd_fast": "12",
    "macd_slow": "26",
    "macd_signal": "9",
    "macd_slope_lookback": "3",
    "macd_enforce_above_zero": "false",
    # Risk / daily limits (web-facing names; None = not explicitly set,
    # _build_settings_response falls back to legacy daily_risk_pct / risk_override_enabled)
    "daily_max_loss_pct": None,
    "daily_profit_target_pct": "7.0",
    "override_risk_per_trade": None,
    "flatten_on_daily_loss": "true",
    "flatten_on_daily_profit": "false",
    # Exits
    "exit_mode": "trail_off",
    "trail_off_trigger": "candle_pattern",
    "trail_off_fraction_per_candle": "0.25",
    "stop_loss_pct": "2.0",
    "take_profit_pct": "4.0",
    "trailing_stop_enabled": "false",
    "force_close_at_close": "true",
}


def get_all_settings_raw(db: DbConn) -> dict[str, str | None]:
    """Return all settings as a raw key→string map with defaults filled in."""
    rows = db.execute("SELECT key, value FROM settings").fetchall()
    result: dict[str, str | None] = dict(SETTING_DEFAULTS)
    for row in rows:
        result[row["key"]] = row["value"]
    return result


def set_setting(db: DbConn, key: str, value: str) -> None:
    now = int(time.time())
    db.execute(
        "INSERT INTO settings (key, value, updated_at) VALUES (%s, %s, %s)"
        " ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = EXCLUDED.updated_at",
        (key, value, now),
    )


def coerce_bool(v: str | None, default: bool = False) -> bool:
    if v is None:
        return default
    return v.lower() in ("true", "1", "yes")


def coerce_int(v: str | None, default: int = 0) -> int:
    if v is None:
        return default
    try:
        return int(v)
    except ValueError:
        return default


def coerce_float(v: str | None, default: float = 0.0) -> float:
    if v is None:
        return default
    try:
        return float(v)
    except ValueError:
        return default


def coerce_list(v: str | None) -> list[str]:
    if not v:
        return []
    try:
        result = json.loads(v)
        return result if isinstance(result, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def serialize_value(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        return json.dumps(value)
    return str(value)


# ─── Tickers ──────────────────────────────────────────────────────────────────


def row_to_ticker(row: object) -> dict:
    r = dict(row)  # type: ignore[call-overload]

    macd_state: dict | None = None
    if r.get("macd_state_json"):
        try:
            macd_state = json.loads(r["macd_state_json"])
        except (json.JSONDecodeError, TypeError):
            pass

    pattern_tags: list[str] = []
    if r.get("pattern_tags_json"):
        try:
            tags = json.loads(r["pattern_tags_json"])
            pattern_tags = tags if isinstance(tags, list) else []
        except (json.JSONDecodeError, TypeError):
            pass

    macd_val = r.get("macd") or 0.0
    sig_val = r.get("signal") or 0.0

    ticker: dict = {
        "symbol": r["symbol"],
        "last_price": r.get("price") or 0.0,
        "high_of_day": r.get("price") or 0.0,
        "low_of_day": r.get("price") or 0.0,
        "macd_line": macd_val,
        "macd_signal": sig_val,
        "macd_hist": macd_val - sig_val,
        "pattern_tags": pattern_tags,
        "score": r.get("score") or 0.0,
        "updated_at": ts_to_iso(r.get("updated_at")) or "1970-01-01T00:00:00Z",
        "float_shares": r.get("float_shares"),
        "unknown_float": bool(r.get("unknown_float", 0)),
        "tradable": bool(r.get("scanner_tradable", 1)),
        "rvol": r.get("rvol"),
        "pct_change": r.get("pct_change"),
        "role": r.get("role"),
    }

    if macd_state:
        ticker["macd_favorability"] = macd_state.get("favorability")
        ticker["macd_eligible"] = macd_state.get("eligible")
    else:
        ticker["macd_favorability"] = None
        ticker["macd_eligible"] = None

    return ticker


def get_all_tickers(db: DbConn) -> list[dict]:
    rows = db.execute("SELECT * FROM active_tickers ORDER BY symbol").fetchall()
    return [row_to_ticker(r) for r in rows]


def get_ticker(db: DbConn, symbol: str) -> dict | None:
    row = db.execute(
        "SELECT * FROM active_tickers WHERE symbol = %s", (symbol,)
    ).fetchone()
    return row_to_ticker(row) if row else None


# ─── Orders ───────────────────────────────────────────────────────────────────


def row_to_order(row: object) -> dict:
    r = dict(row)  # type: ignore[call-overload]
    side = r.get("side", "buy")
    order_type = r.get("order_type", "market")

    schema_type = "limit" if order_type in ("limit", "stop") else side

    submitted_price = r.get("limit_price") or r.get("stop_price") or 0.0

    return {
        "id": r["id"],
        "type": schema_type,
        "symbol": r["symbol"],
        "qty": r.get("quantity") or 0.0,
        "submitted_price": submitted_price,
        "status": r.get("status", "pending"),
        "filled_qty": r.get("filled_quantity"),
        "filled_price": r.get("filled_price"),
        "submitted_at": ts_to_iso(r.get("created_at")),
        "updated_at": ts_to_iso(r.get("updated_at")),
    }


def get_order(db: DbConn, order_id: str) -> dict | None:
    row = db.execute("SELECT * FROM orders WHERE id = %s", (order_id,)).fetchone()
    return row_to_order(row) if row else None


# ─── Trades ───────────────────────────────────────────────────────────────────


def get_trade_history(
    db: DbConn, limit: int = 100, offset: int = 0
) -> tuple[list[dict], int]:
    total_row = db.execute("SELECT COUNT(*) AS cnt FROM trades").fetchone()
    total = total_row["cnt"] if total_row else 0
    rows = db.execute(
        "SELECT * FROM trades ORDER BY opened_at DESC LIMIT %s OFFSET %s",
        (limit, offset),
    ).fetchall()

    trades = []
    for row in rows:
        r = dict(row)  # type: ignore[call-overload]
        entry = get_order(db, r["entry_order_id"])
        exit_ = get_order(db, r["exit_order_id"]) if r.get("exit_order_id") else None
        trades.append(
            {
                "id": r["id"],
                "symbol": r["symbol"],
                "entry_order": entry,
                "exit_order": exit_,
                "net_pl": r.get("net_pnl") or 0.0,
                "label": r.get("label") or "bad",
                "opened_at": ts_to_iso(r.get("opened_at")),
                "closed_at": ts_to_iso(r.get("closed_at")),
            }
        )
    return trades, total


# ─── Lists ────────────────────────────────────────────────────────────────────


def get_list_symbols(db: DbConn, list_type: str) -> list[str]:
    rows = db.execute(
        "SELECT symbol FROM lists WHERE list_type = %s AND active = 1 ORDER BY symbol",
        (list_type,),
    ).fetchall()
    return [r["symbol"] for r in rows]


def replace_list(db: DbConn, list_type: str, symbols: list[str]) -> None:
    now = int(time.time())
    db.execute("UPDATE lists SET active = 0 WHERE list_type = %s", (list_type,))
    for sym in symbols:
        db.execute(
            "INSERT INTO lists (symbol, list_type, active, added_at)"
            " VALUES (%s, %s, 1, %s)"
            " ON CONFLICT (symbol, list_type)"
            " DO UPDATE SET active = 1, added_at = EXCLUDED.added_at",
            (sym, list_type, now),
        )
    db.commit()


# ─── Run-day tracking ─────────────────────────────────────────────────────────


def mark_run_day(db: DbConn, date: str | None = None) -> None:
    if date is None:
        date = datetime.date.today().isoformat()
    now = int(time.time())
    db.execute(
        "INSERT INTO run_days (date, marked_at) VALUES (%s, %s)"
        " ON CONFLICT (date) DO UPDATE SET marked_at = EXCLUDED.marked_at",
        (date, now),
    )
    db.commit()


def get_run_days(db: DbConn, start: str, end: str) -> list[str]:
    rows = db.execute(
        "SELECT date FROM run_days WHERE date >= %s AND date <= %s ORDER BY date",
        (start, end),
    ).fetchall()
    return [r["date"] for r in rows]


# ─── Daily P/L ────────────────────────────────────────────────────────────────


def get_daily_pl(db: DbConn, start: str, end: str) -> list[dict]:
    run_days = get_run_days(db, start, end)
    if not run_days:
        return []

    results = []
    for date_str in run_days:
        try:
            d = datetime.date.fromisoformat(date_str)
        except ValueError:
            continue
        day_start = int(
            datetime.datetime(
                d.year, d.month, d.day, tzinfo=datetime.timezone.utc
            ).timestamp()
        )
        day_end = day_start + 86400

        rows = db.execute(
            "SELECT net_pnl FROM trades"
            " WHERE status = 'closed' AND closed_at >= %s AND closed_at < %s",
            (day_start, day_end),
        ).fetchall()

        trade_count = len(rows)
        net_pl = sum(r["net_pnl"] or 0.0 for r in rows)

        if trade_count == 0 or net_pl == 0:
            color = "blue"
        elif net_pl > 0:
            color = "green"
        else:
            color = "red"

        results.append(
            {
                "date": date_str,
                "ran": True,
                "net_pl": net_pl,
                "trade_count": trade_count,
                "color": color,
            }
        )
    return results
