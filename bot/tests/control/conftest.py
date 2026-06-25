"""Shared fixtures for control-service tests."""

from __future__ import annotations

import sqlite3
import time
import uuid

import pytest


# ─── Full DB schema (migrations 001–004 inlined) ──────────────────────────────

_SCHEMA_SQL = """
CREATE TABLE settings (
  key        TEXT    PRIMARY KEY,
  value      TEXT    NOT NULL,
  updated_at INTEGER NOT NULL
);

CREATE TABLE active_tickers (
  symbol          TEXT    PRIMARY KEY,
  price           REAL    NOT NULL,
  volume          REAL    NOT NULL,
  rsi             REAL,
  macd            REAL,
  signal          REAL,
  ema_short       REAL,
  ema_long        REAL,
  state           TEXT    NOT NULL,
  updated_at      INTEGER NOT NULL,
  gap_pct         REAL,
  rvol            REAL,
  float_shares    INTEGER,
  unknown_float   INTEGER NOT NULL DEFAULT 0,
  scanner_tradable INTEGER NOT NULL DEFAULT 1,
  pct_change      REAL,
  macd_state_json TEXT,
  pattern_tags_json TEXT,
  pattern_sig_json  TEXT,
  role            TEXT,
  score           REAL
);

CREATE TABLE orders (
  id              TEXT    PRIMARY KEY,
  symbol          TEXT    NOT NULL,
  side            TEXT    NOT NULL,
  order_type      TEXT    NOT NULL,
  quantity        REAL    NOT NULL,
  limit_price     REAL,
  stop_price      REAL,
  filled_price    REAL,
  filled_quantity REAL,
  status          TEXT    NOT NULL,
  broker_order_id TEXT,
  created_at      INTEGER NOT NULL,
  updated_at      INTEGER NOT NULL
);

CREATE TABLE order_status_events (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  order_id        TEXT    NOT NULL REFERENCES orders(id),
  status          TEXT    NOT NULL,
  filled_price    REAL,
  filled_quantity REAL,
  message         TEXT,
  occurred_at     INTEGER NOT NULL
);

CREATE TABLE trades (
  id             TEXT    PRIMARY KEY,
  symbol         TEXT    NOT NULL,
  entry_order_id TEXT    NOT NULL REFERENCES orders(id),
  exit_order_id  TEXT    REFERENCES orders(id),
  entry_price    REAL    NOT NULL,
  exit_price     REAL,
  quantity       REAL    NOT NULL,
  gross_pnl      REAL,
  net_pnl        REAL,
  fees           REAL    NOT NULL DEFAULT 0,
  label          TEXT,
  status         TEXT    NOT NULL,
  opened_at      INTEGER NOT NULL,
  closed_at      INTEGER
);

CREATE TABLE log_events (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  level       TEXT    NOT NULL,
  message     TEXT    NOT NULL,
  context     TEXT,
  occurred_at INTEGER NOT NULL
);

CREATE TABLE lists (
  id        INTEGER PRIMARY KEY AUTOINCREMENT,
  symbol    TEXT    NOT NULL,
  list_type TEXT    NOT NULL,
  reason    TEXT,
  active    INTEGER NOT NULL DEFAULT 1,
  added_at  INTEGER NOT NULL,
  UNIQUE(symbol, list_type)
);

CREATE TABLE ml_samples (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  symbol        TEXT    NOT NULL,
  features      TEXT    NOT NULL,
  label         INTEGER,
  model_version TEXT,
  trade_id      TEXT    REFERENCES trades(id),
  sampled_at    INTEGER NOT NULL
);

CREATE TABLE run_days (
  date       TEXT    PRIMARY KEY,
  marked_at  INTEGER NOT NULL
);
"""

_DEFAULT_SETTINGS = [
    ("bot_id", str(uuid.uuid4())),
    ("relay_url", "wss://relay.example.com"),
    ("license_key", "test-license-key"),
    ("connection_password", "test-password"),
    ("paper_trading", "true"),
    ("broker", "alpaca"),
    ("max_positions", "5"),
    ("risk_per_trade_pct", "1.0"),
    ("daily_risk_pct", "5.0"),
    ("risk_override_enabled", "false"),
    ("min_score", "60.0"),
    ("auto_trade", "false"),
    ("macd_fast", "12"),
    ("macd_slow", "26"),
    ("macd_signal", "9"),
    ("log_level", "info"),
]


@pytest.fixture
def db() -> sqlite3.Connection:
    """In-memory SQLite DB with the full schema and default settings seeded."""
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(_SCHEMA_SQL)
    now = int(time.time())
    conn.executemany(
        "INSERT OR IGNORE INTO settings (key, value, updated_at) VALUES (?, ?, ?)",
        [(k, v, now) for k, v in _DEFAULT_SETTINGS],
    )
    conn.commit()
    yield conn
    conn.close()


# ─── Convenience helpers ──────────────────────────────────────────────────────


def insert_order(
    conn: sqlite3.Connection,
    *,
    order_id: str | None = None,
    symbol: str = "AAPL",
    side: str = "buy",
    order_type: str = "market",
    quantity: float = 10.0,
    limit_price: float | None = None,
    status: str = "filled",
    filled_price: float = 5.00,
    filled_quantity: float = 10.0,
) -> str:
    oid = order_id or str(uuid.uuid4())
    now = int(time.time())
    conn.execute(
        """INSERT INTO orders
           (id, symbol, side, order_type, quantity, limit_price,
            filled_price, filled_quantity, status, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (oid, symbol, side, order_type, quantity, limit_price,
         filled_price, filled_quantity, status, now, now),
    )
    conn.commit()
    return oid


def insert_trade(
    conn: sqlite3.Connection,
    *,
    trade_id: str | None = None,
    symbol: str = "AAPL",
    entry_order_id: str,
    exit_order_id: str | None = None,
    entry_price: float = 5.00,
    exit_price: float | None = None,
    net_pnl: float = 0.0,
    status: str = "closed",
    label: str = "good",
    closed_at: int | None = None,
) -> str:
    tid = trade_id or str(uuid.uuid4())
    now = int(time.time())
    conn.execute(
        """INSERT INTO trades
           (id, symbol, entry_order_id, exit_order_id,
            entry_price, exit_price, quantity, net_pnl,
            fees, label, status, opened_at, closed_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (tid, symbol, entry_order_id, exit_order_id,
         entry_price, exit_price, 10.0, net_pnl,
         0.0, label, status, now, closed_at or now),
    )
    conn.commit()
    return tid


def insert_ticker(
    conn: sqlite3.Connection,
    *,
    symbol: str = "AAPL",
    price: float = 10.0,
    volume: float = 1_000_000.0,
    rvol: float = 3.5,
    float_shares: int | None = 5_000_000,
    unknown_float: bool = False,
    scanner_tradable: bool = True,
    pct_change: float = 8.5,
    macd: float = 0.05,
    signal: float = 0.02,
    role: str = "leader",
    score: float = 75.0,
    macd_state_json: str | None = None,
) -> None:
    import json as _json

    now = int(time.time())
    default_macd_state = _json.dumps(
        {"value": macd, "slope": 0.01, "hist": macd - signal,
         "favorability": 0.8, "eligible": True}
    )
    conn.execute(
        """INSERT OR REPLACE INTO active_tickers
           (symbol, price, volume, macd, signal, state, updated_at,
            rvol, float_shares, unknown_float, scanner_tradable,
            pct_change, role, score, macd_state_json)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            symbol, price, volume, macd, signal, "watching", now,
            rvol, float_shares, 1 if unknown_float else 0,
            1 if scanner_tradable else 0,
            pct_change, role, score,
            macd_state_json or default_macd_state,
        ),
    )
    conn.commit()
