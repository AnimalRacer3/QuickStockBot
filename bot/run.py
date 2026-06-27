"""
QuickStockBot trading engine — standalone entry point.

Reads config from ~/.quickstockbot/ (or %LOCALAPPDATA%\\QuickStockBot\\ on Windows),
then starts the relay client and local API server concurrently.
"""

from __future__ import annotations

import asyncio
import logging
import logging.handlers
import os
import platform
import sqlite3
import sys
from pathlib import Path


def _config_dir() -> Path:
    if platform.system() == "Windows":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home())
        return Path(base) / "QuickStockBot"
    return Path.home() / ".quickstockbot"


def _pause_on_windows() -> None:
    """Keep the console window open on Windows so the user can read the output."""
    if platform.system() == "Windows":
        try:
            input("\nPress Enter to exit...")
        except (EOFError, KeyboardInterrupt):
            pass


def _setup_file_logging(config_dir: Path) -> None:
    """Add a rotating file handler so logs persist after the window closes."""
    log_path = config_dir / "quickstockbot.log"
    handler = logging.handlers.RotatingFileHandler(
        log_path, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    logging.getLogger().addHandler(handler)
    print(f"[QuickStockBot] Logging to {log_path}", flush=True)


_SCHEMA_SQL = """
    CREATE TABLE IF NOT EXISTS settings (
        key        TEXT    PRIMARY KEY,
        value      TEXT    NOT NULL,
        updated_at INTEGER NOT NULL
    );

    CREATE TABLE IF NOT EXISTS active_tickers (
        symbol            TEXT    PRIMARY KEY,
        price             REAL    NOT NULL,
        volume            REAL    NOT NULL,
        rsi               REAL,
        macd              REAL,
        signal            REAL,
        ema_short         REAL,
        ema_long          REAL,
        state             TEXT    NOT NULL DEFAULT 'watching',
        updated_at        INTEGER NOT NULL,
        gap_pct           REAL,
        rvol              REAL,
        float_shares      INTEGER,
        unknown_float     INTEGER NOT NULL DEFAULT 0,
        scanner_tradable  INTEGER NOT NULL DEFAULT 1,
        pct_change        REAL,
        macd_state_json   TEXT,
        pattern_tags_json TEXT,
        pattern_sig_json  TEXT,
        role              TEXT,
        score             REAL
    );

    CREATE TABLE IF NOT EXISTS orders (
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

    CREATE TABLE IF NOT EXISTS order_status_events (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id        TEXT    NOT NULL REFERENCES orders(id),
        status          TEXT    NOT NULL,
        filled_price    REAL,
        filled_quantity REAL,
        message         TEXT,
        occurred_at     INTEGER NOT NULL
    );

    CREATE TABLE IF NOT EXISTS trades (
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

    CREATE TABLE IF NOT EXISTS log_events (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        level       TEXT    NOT NULL,
        message     TEXT    NOT NULL,
        context     TEXT,
        occurred_at INTEGER NOT NULL
    );

    CREATE TABLE IF NOT EXISTS lists (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol    TEXT    NOT NULL,
        list_type TEXT    NOT NULL,
        reason    TEXT,
        active    INTEGER NOT NULL DEFAULT 1,
        added_at  INTEGER NOT NULL,
        UNIQUE(symbol, list_type)
    );

    CREATE TABLE IF NOT EXISTS ml_samples (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol        TEXT    NOT NULL,
        features      TEXT    NOT NULL,
        label         INTEGER,
        model_version TEXT,
        trade_id      TEXT    REFERENCES trades(id),
        sampled_at    INTEGER NOT NULL
    );

    CREATE TABLE IF NOT EXISTS ticker_profit_stats (
        symbol         TEXT    PRIMARY KEY,
        cumulative_pnl REAL    NOT NULL DEFAULT 0.0,
        trade_count    INTEGER NOT NULL DEFAULT 0,
        win_count      INTEGER NOT NULL DEFAULT 0,
        updated_at     INTEGER NOT NULL
    );

    CREATE TABLE IF NOT EXISTS daily_efficiency (
        date           TEXT    PRIMARY KEY,
        trades_to_goal INTEGER NOT NULL,
        goal_reached   INTEGER NOT NULL DEFAULT 0,
        daily_pnl_pct  REAL    NOT NULL DEFAULT 0.0,
        recorded_at    INTEGER NOT NULL
    );

    CREATE TABLE IF NOT EXISTS run_days (
        date      TEXT    PRIMARY KEY,
        marked_at INTEGER NOT NULL
    );

    CREATE INDEX IF NOT EXISTS idx_order_status_events_order_id ON order_status_events(order_id);
    CREATE INDEX IF NOT EXISTS idx_order_status_events_occurred  ON order_status_events(occurred_at);
    CREATE INDEX IF NOT EXISTS idx_trades_entry_order_id         ON trades(entry_order_id);
    CREATE INDEX IF NOT EXISTS idx_trades_exit_order_id          ON trades(exit_order_id);
    CREATE INDEX IF NOT EXISTS idx_log_events_occurred           ON log_events(occurred_at);
    CREATE INDEX IF NOT EXISTS idx_lists_symbol                  ON lists(symbol);
    CREATE INDEX IF NOT EXISTS idx_ml_samples_trade_id           ON ml_samples(trade_id);
"""

_REQUIRED_ENV_VARS = ("RELAY_URL", "BOT_ID", "LICENSE_KEY", "CONNECTION_PASSWORD")


def _init_db(db: sqlite3.Connection) -> None:
    """Create all tables and indexes if they don't exist yet (idempotent)."""
    db.executescript(_SCHEMA_SQL)
    db.commit()


def main() -> None:
    config_dir = _config_dir()
    env_file = config_dir / ".env"

    if not env_file.exists():
        print(
            f"[QuickStockBot] Config not found at {env_file}.\n"
            "Run the installer (quickstockbot-installer) first.",
            file=sys.stderr,
            flush=True,
        )
        _pause_on_windows()
        sys.exit(1)

    from dotenv import load_dotenv

    load_dotenv(env_file, override=True)

    missing = [k for k in _REQUIRED_ENV_VARS if not os.environ.get(k)]
    if missing:
        print(
            f"[QuickStockBot] Missing required settings in {env_file}:\n"
            + "\n".join(f"  - {k}" for k in missing)
            + "\n\nRe-run the installer (quickstockbot-installer) to fix your configuration.",
            file=sys.stderr,
            flush=True,
        )
        _pause_on_windows()
        sys.exit(1)

    logging.basicConfig(
        level=getattr(
            logging, os.environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO
        ),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    config_dir.mkdir(parents=True, exist_ok=True)
    _setup_file_logging(config_dir)

    logger = logging.getLogger(__name__)
    logger.info("Starting QuickStockBot (config: %s)", config_dir)

    try:
        asyncio.run(_run(config_dir))
    except KeyboardInterrupt:
        logger.info("Shutting down (keyboard interrupt).")
    except Exception:
        logger.exception("Fatal error — bot is stopping.")
        _pause_on_windows()
        sys.exit(1)


async def _run(config_dir: Path) -> None:
    import uvicorn

    import bot.control.local_api as _local_api_mod
    from bot.control.relay_client import RelayClient

    db_path = str(config_dir / "quickstock.db")
    db = sqlite3.connect(db_path, check_same_thread=False)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    _init_db(db)

    _local_api_mod._db_path = db_path

    relay = RelayClient(
        url=os.environ["RELAY_URL"],
        bot_id=os.environ["BOT_ID"],
        license_key=os.environ["LICENSE_KEY"],
        connection_password=os.environ["CONNECTION_PASSWORD"],
        db=db,
    )

    uv_config = uvicorn.Config(
        _local_api_mod.app, host="127.0.0.1", port=8765, log_level="warning"
    )
    server = uvicorn.Server(uv_config)

    await asyncio.gather(relay.run(), server.serve())


if __name__ == "__main__":
    main()
