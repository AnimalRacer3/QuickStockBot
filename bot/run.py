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

# Maps Python import name → pip install name for every third-party dependency.
_REQUIRED_PACKAGES: dict[str, str] = {
    "dotenv": "python-dotenv",
    "fastapi": "fastapi",
    "uvicorn": "uvicorn",
    "httpx": "httpx",
    "websockets": "websockets",
    "pydantic": "pydantic",
    "tenacity": "tenacity",
    "sklearn": "scikit-learn",
    "anyio": "anyio",
}


def _check_and_install_deps() -> bool:
    """
    Verify all third-party packages are importable.

    - If running as a frozen PyInstaller bundle: just report what is missing
      (pip is not available inside the bundle).
    - If running from a normal Python environment: attempt a pip install for
      each missing package, then re-check.

    Returns True when all dependencies are satisfied, False otherwise.
    """
    import subprocess

    missing = {
        mod: pkg for mod, pkg in _REQUIRED_PACKAGES.items() if not _try_import(mod)
    }

    if not missing:
        return True

    is_frozen = getattr(sys, "frozen", False)

    if is_frozen:
        print(
            "\n[QuickStockBot] ERROR — one or more bundled modules could not be loaded.\n"
            "This usually means the installation is corrupt.\n\n"
            "Missing modules:\n"
            + "\n".join(f"  - {mod}  (package: {pkg})" for mod, pkg in missing.items())
            + "\n\nPlease re-download and reinstall QuickStockBot.",
            file=sys.stderr,
            flush=True,
        )
        return False

    # Non-frozen: try to install with pip.
    pkgs = list(missing.values())
    print(
        f"[QuickStockBot] Missing packages: {', '.join(pkgs)}\n"
        "Attempting automatic installation...",
        flush=True,
    )

    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--quiet"] + pkgs,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print(
            "[QuickStockBot] Automatic installation failed.\n\n"
            "pip output:\n"
            + (result.stderr or result.stdout or "(no output)")
            + "\n\nInstall the missing packages manually and try again:\n"
            f"  pip install {' '.join(pkgs)}",
            file=sys.stderr,
            flush=True,
        )
        return False

    # Re-check after install.
    still_missing = {mod: pkg for mod, pkg in missing.items() if not _try_import(mod)}
    if still_missing:
        print(
            "[QuickStockBot] Installation appeared to succeed but modules are still "
            "not importable:\n"
            + "\n".join(
                f"  - {mod}  (package: {pkg})" for mod, pkg in still_missing.items()
            )
            + "\n\nInstall them manually and try again:\n"
            f"  pip install {' '.join(still_missing.values())}",
            file=sys.stderr,
            flush=True,
        )
        return False

    print("[QuickStockBot] Dependencies installed successfully.", flush=True)
    return True


def _try_import(module: str) -> bool:
    import importlib

    try:
        importlib.import_module(module)
        return True
    except ImportError:
        return False


# ── Error diagnosis ──────────────────────────────────────────────────────────


def _diagnose_error(exc: BaseException, config_dir: Path) -> str:
    """
    Return a human-readable explanation and suggested fix for a fatal startup
    exception.  Falls back to a generic message so something always prints.
    """
    name = type(exc).__name__
    msg = str(exc).lower()

    lines: list[str] = []

    # --- WebSocket / network connection failures ---
    if name in ("ConnectionRefusedError", "ConnectionResetError") or (
        name in ("OSError", "gaierror") and "connect" in msg
    ):
        lines += [
            "Cannot connect to the relay server.",
            "",
            "Possible fixes:",
            "  1. Check that your internet connection is working.",
            f"  2. Verify RELAY_URL in your config file ({config_dir / '.env'}) is correct.",
            "  3. Re-run the installer (quickstockbot-installer) to reset your relay URL.",
        ]

    elif (
        "nodename nor servname provided" in msg
        or "name or service not known" in msg
        or (name in ("gaierror", "socket.gaierror"))
    ):
        lines += [
            "DNS lookup failed — the relay server hostname could not be resolved.",
            "",
            "Possible fixes:",
            "  1. Check your internet connection.",
            f"  2. Verify RELAY_URL in {config_dir / '.env'} contains a valid hostname.",
            "  3. Re-run the installer (quickstockbot-installer) to reset your relay URL.",
        ]

    # --- WebSocket handshake / TLS errors ---
    elif "ssl" in msg or "certificate" in msg or "tls" in msg:
        lines += [
            "SSL/TLS error while connecting to the relay server.",
            "",
            "Possible fixes:",
            "  1. Ensure your system clock is correct (TLS certificates are time-sensitive).",
            "  2. Check that your antivirus / firewall is not intercepting HTTPS traffic.",
            "  3. Re-run the installer (quickstockbot-installer) to reset your relay URL.",
        ]

    # --- Authentication / registration rejected ---
    elif (
        "auth" in msg
        or "forbidden" in msg
        or "401" in msg
        or "403" in msg
        or (name == "RuntimeError" and ("auth_challenge" in msg or "register" in msg))
    ):
        lines += [
            "Authentication with the relay server failed.",
            "",
            "Possible fixes:",
            f"  1. Check that BOT_ID, LICENSE_KEY, and CONNECTION_PASSWORD in {config_dir / '.env'}",
            "     match the values shown in your QuickStockBot dashboard.",
            "  2. Re-run the installer (quickstockbot-installer) to re-enter your credentials.",
        ]

    # --- Port already in use (local API server) ---
    elif (
        "address already in use" in msg
        or "10048" in msg
        or "10013" in msg
        or (name == "OSError" and "bind" in msg)
    ):
        lines += [
            "Port 8765 is already in use — the local API server could not start.",
            "",
            "Possible fixes:",
            "  1. Close any other QuickStockBot instances that may still be running.",
            "  2. Open Task Manager and end any 'quickstockbot' processes.",
            "  3. Restart your computer if the port remains occupied.",
        ]

    # --- SQLite / database errors ---
    elif "sqlite" in name.lower() or "database" in msg or "db" in name.lower():
        db_path = config_dir / "quickstock.db"
        lines += [
            "Database error — the local database could not be opened or initialised.",
            "",
            "Possible fixes:",
            f"  1. Check that the folder exists and is writable: {config_dir}",
            f"  2. If the database file is corrupted, delete it and restart: {db_path}",
            "     (Trade history will be lost, but the bot will recreate the file.)",
        ]

    # --- Import / packaging errors (frozen exe) ---
    elif name in ("ModuleNotFoundError", "ImportError"):
        lines += [
            f"A required module could not be loaded: {exc}",
            "",
            "Possible fixes:",
            "  1. Download and install the latest version of QuickStockBot.",
            "  2. If this persists, contact support with the log file below.",
        ]

    # --- Fallback: show the raw exception clearly ---
    else:
        lines += [
            f"An unexpected error occurred ({name}):",
            f"  {exc}",
            "",
            "Possible fixes:",
            "  1. Re-run the installer (quickstockbot-installer) to reset your configuration.",
            "  2. Restart your computer and try again.",
            "  3. Check the log file for more detail (path shown below).",
        ]

    log_path = config_dir / "quickstockbot.log"
    lines += [
        "",
        f"Full error details have been written to: {log_path}",
        "Share that file with support if the problem persists.",
    ]
    return "\n".join(lines)


def _init_db(db: sqlite3.Connection) -> None:
    """Create all tables and indexes if they don't exist yet (idempotent)."""
    db.executescript(_SCHEMA_SQL)
    db.commit()


def main() -> None:
    config_dir = _config_dir()

    if not _check_and_install_deps():
        _pause_on_windows()
        sys.exit(1)

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

    try:
        from dotenv import load_dotenv
    except ImportError as exc:
        print(
            f"[QuickStockBot] Cannot import 'dotenv': {exc}\n"
            "Run:  pip install python-dotenv",
            file=sys.stderr,
            flush=True,
        )
        _pause_on_windows()
        sys.exit(1)

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
    except Exception as exc:
        logger.exception("Fatal error — bot is stopping.")
        diagnosis = _diagnose_error(exc, config_dir)
        print(
            "\n" + "=" * 60 + "\n"
            "  QuickStockBot stopped due to an error\n"
            "=" * 60 + "\n\n" + diagnosis,
            file=sys.stderr,
            flush=True,
        )
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
    try:
        main()
    except SystemExit:
        raise  # let sys.exit() pass through normally
    except Exception:
        import traceback

        print(
            "\n" + "=" * 60 + "\n"
            "  QuickStockBot crashed before startup completed\n"
            "=" * 60 + "\n",
            file=sys.stderr,
            flush=True,
        )
        traceback.print_exc(file=sys.stderr)
        print(
            "\nThis is likely a bundling or environment issue.\n"
            "Please reinstall QuickStockBot or contact support.",
            file=sys.stderr,
            flush=True,
        )
        _pause_on_windows()
        sys.exit(1)
