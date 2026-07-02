"""CLI entrypoint for trader.exe.

Usage:
    trader.exe                  Run the normal daily lifecycle (live scheduler use).
    trader.exe --selftest       Check env/Alpaca/MCP/Anthropic connectivity; PASS/FAIL table.
    trader.exe --replay DATE    Replay a recorded day (YYYY-MM-DD) against the engine.
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date

from trader.config import ConfigError, load_config, load_secrets


def _run_normal() -> int:
    from trader.engine import EXIT_CONFIG_ERROR, EXIT_DATA_FEED_ERROR, run_live_day

    try:
        config = load_config()
        secrets = load_secrets()
    except ConfigError as exc:
        print(f"Config/secrets error: {exc}", file=sys.stderr)
        return EXIT_CONFIG_ERROR

    try:
        return run_live_day(config, secrets)
    except Exception as exc:  # noqa: BLE001 - top-level safety net; never crash without an exit code
        logging.getLogger("trader").exception("Unhandled error during trading day")
        print(f"Unhandled error: {exc}", file=sys.stderr)
        return EXIT_DATA_FEED_ERROR


def _run_replay(date_str: str) -> int:
    from trader.replay import ReplayError, run_replay

    try:
        replay_date = date.fromisoformat(date_str)
    except ValueError:
        print(f"Invalid date {date_str!r}; expected YYYY-MM-DD", file=sys.stderr)
        return 3

    try:
        config = load_config()
    except ConfigError as exc:
        print(f"Config error: {exc}", file=sys.stderr)
        return 3

    try:
        return run_replay(config, replay_date)
    except ReplayError as exc:
        print(f"Replay error: {exc}", file=sys.stderr)
        return 3


def _run_selftest() -> int:
    from trader.selftest import run_selftest

    return run_selftest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="trader", description="QuickStockBot day-trading engine")
    parser.add_argument("--selftest", action="store_true", help="Check connectivity and exit")
    parser.add_argument("--replay", metavar="DATE", help="Replay a recorded day (YYYY-MM-DD)")
    args = parser.parse_args(argv)

    if args.selftest:
        return _run_selftest()
    if args.replay:
        return _run_replay(args.replay)
    return _run_normal()


if __name__ == "__main__":
    sys.exit(main())
