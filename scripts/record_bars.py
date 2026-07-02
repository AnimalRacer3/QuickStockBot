#!/usr/bin/env python3
"""Record a day's Alpaca 1-minute bars (and a watchlist) to
`trading/replay/` so `trader.exe --replay <date>` can validate patterns
without waiting for market hours.

Usage:
    python scripts/record_bars.py --date 2026-06-15 --tickers AAPL,TSLA,NVDA
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from trader.alpaca_data import AlpacaData, AlpacaDataError  # noqa: E402
from trader.config import load_config, load_secrets  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Record a day of Alpaca bars for --replay")
    parser.add_argument("--date", required=True, help="Date to record, YYYY-MM-DD (e.g. 2026-06-15)")
    parser.add_argument("--tickers", required=True, help="Comma-separated tickers, e.g. AAPL,TSLA")
    args = parser.parse_args()

    try:
        record_date = date.fromisoformat(args.date)
    except ValueError:
        print(f"--date must be YYYY-MM-DD (got {args.date!r}, e.g. 2026-06-15)", file=sys.stderr)
        return 2
    if record_date >= date.today():
        print(
            f"WARNING: {record_date} is today or in the future. Alpaca's free/basic data plan "
            "restricts querying data from roughly the last 15 minutes -- record a fully "
            "completed past trading day instead (--replay is meant for backtesting, not "
            "watching today live)."
        )
    tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]

    config = load_config()
    secrets = load_secrets()
    alpaca = AlpacaData(secrets.alpaca_key, secrets.alpaca_secret, paper=True, feed=config.alpaca_data_feed)
    config.paths.ensure()

    watchlist = []
    for rank, ticker in enumerate(tickers, start=1):
        try:
            bars = alpaca.get_minute_bars_for_day(ticker, record_date)
        except AlpacaDataError as exc:
            if "sip" in str(exc).lower():
                print(
                    f"ERROR fetching {ticker}: {exc}\n"
                    "  Your Alpaca plan doesn't permit recent SIP data. This request already uses "
                    "config.yaml's alpaca_data_feed (default 'iex'), so if you're still seeing this, "
                    "pick a date further in the past or check your Alpaca market-data subscription tier."
                )
            else:
                print(f"ERROR fetching {ticker}: {exc}")
            continue
        if not bars:
            print(f"WARNING: no bars returned for {ticker} on {record_date}; skipping.")
            continue

        out_path = config.paths.replay_dir / f"{record_date.isoformat()}-{ticker}.json"
        payload = [
            {
                "timestamp": c.timestamp.isoformat(),
                "open": c.open,
                "high": c.high,
                "low": c.low,
                "close": c.close,
                "volume": c.volume,
            }
            for c in bars
        ]
        out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"Wrote {len(bars)} bars for {ticker} -> {out_path}")

        watchlist.append({"ticker": ticker, "reason": "recorded fixture", "catalyst": "n/a", "rank": rank})

    if not watchlist:
        print("No tickers recorded; not writing a watchlist file.")
        return 1

    watchlist_path = config.paths.replay_dir / f"{record_date.isoformat()}-watchlist.json"
    watchlist_path.write_text(json.dumps(watchlist, indent=2), encoding="utf-8")
    print(f"Wrote watchlist -> {watchlist_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
