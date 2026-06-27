"""
QuickStockBot trading engine — standalone entry point.

Reads config from ~/.quickstockbot/ (or %LOCALAPPDATA%\\QuickStockBot\\ on Windows),
then starts the relay client and local API server concurrently.
"""
from __future__ import annotations

import asyncio
import logging
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


def main() -> None:
    config_dir = _config_dir()
    env_file = config_dir / ".env"

    if not env_file.exists():
        print(
            f"[QuickStockBot] Config not found at {env_file}.\n"
            "Run the installer (quickstockbot-installer) first.",
            file=sys.stderr,
        )
        sys.exit(1)

    from dotenv import load_dotenv

    load_dotenv(env_file, override=True)

    logging.basicConfig(
        level=getattr(
            logging, os.environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO
        ),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    asyncio.run(_run(config_dir))


async def _run(config_dir: Path) -> None:
    import uvicorn

    import bot.control.local_api as _local_api_mod
    from bot.control.relay_client import RelayClient

    db_path = str(config_dir / "quickstock.db")
    db = sqlite3.connect(db_path, check_same_thread=False)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")

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
