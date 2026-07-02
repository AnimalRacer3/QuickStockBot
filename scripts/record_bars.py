#!/usr/bin/env python3
"""Record a day's Alpaca 1-minute bars (and a watchlist) to
`trading/replay/` so `trader.exe --replay <date>` can validate patterns
without waiting for market hours.

Usage:
    python scripts/record_bars.py --date 2026-06-15 --tickers AAPL,TSLA,NVDA

    # Point at a trader.exe distribution directory's own config.yaml so
    # fixtures land exactly where that trader.exe will look for them:
    python scripts/record_bars.py --date 2026-06-15 --tickers AAPL \\
        --config C:\\trading-bot\\config.yaml
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


def _load_existing_watchlist(path: Path) -> dict[str, dict]:
    """Keyed by ticker so a re-recording of the same date/ticker overwrites
    that entry in place instead of duplicating it, while other tickers
    recorded earlier for the same date are preserved."""
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {row["ticker"]: row for row in raw}


def main() -> int:
    parser = argparse.ArgumentParser(description="Record a day of Alpaca bars for --replay")
    parser.add_argument("--date", required=True, help="Date to record, YYYY-MM-DD (e.g. 2026-06-15)")
    parser.add_argument("--tickers", required=True, help="Comma-separated tickers, e.g. AAPL,TSLA")
    parser.add_argument(
        "--config", default=None,
        help="Path to the config.yaml to use (e.g. the one next to your trader.exe build). "
        "Defaults to this repo's own config.yaml. Fixtures are written under that config's "
        "paths.replay_dir, so pointing this at a trader.exe distribution's config.yaml means "
        "no manual copying is needed for --replay to find them there.",
    )
    args = parser.parse_args()

    try:
        record_date = date.fromisoformat(args.date)
    except ValueError:
        print(f"--date must be YYYY-MM-DD (got {args.date!r}, e.g. 2026-06-15)", file=sys.stderr)
        return 2
    if record_date >= date.today():
        print(
            f"NOTE: {record_date} is today. Alpaca's free/basic plan restricts the SIP feed to "
            "data older than ~15 minutes, so this recording will use the real-time IEX feed "
            "instead. IEX prints thinner volume than the full consolidated (SIP) tape, so "
            "recorded volume -- and any RVOL baseline computed from it -- will read lower than "
            "the true market-wide total. Keep that in mind when replaying today's fixture."
        )
    tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]

    config_path = Path(args.config).resolve() if args.config else None
    config = load_config(config_path)
    secrets = load_secrets(config_path.parent / ".env" if config_path else None)
    alpaca = AlpacaData(secrets.alpaca_key, secrets.alpaca_secret, paper=True, feed=config.alpaca_data_feed)
    config.paths.ensure()

    watchlist_path = config.paths.replay_dir / f"{record_date.isoformat()}-watchlist.json"
    watchlist_by_ticker = _load_existing_watchlist(watchlist_path)
    next_rank = (max((row["rank"] for row in watchlist_by_ticker.values()), default=0)) + 1

    recorded_any = False
    for ticker in tickers:
        try:
            bars = alpaca.get_minute_bars_for_day(ticker, record_date)
        except AlpacaDataError as exc:
            if "sip" in str(exc).lower():
                print(
                    f"ERROR fetching {ticker}: {exc}\n"
                    "  Your Alpaca plan doesn't permit recent SIP data. This request already uses "
                    "IEX for any range touching today, so if you're still seeing this, check your "
                    "Alpaca market-data subscription tier."
                )
            else:
                print(f"ERROR fetching {ticker}: {exc}")
            continue
        if not bars:
            print(f"WARNING: no bars returned for {ticker} on {record_date}; skipping.")
            continue

        try:
            avg_volume_baseline = alpaca.get_avg_daily_volume(ticker)
        except AlpacaDataError as exc:
            print(f"WARNING: could not fetch avg daily volume baseline for {ticker}: {exc}")
            avg_volume_baseline = None

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

        rank = watchlist_by_ticker[ticker]["rank"] if ticker in watchlist_by_ticker else next_rank
        if ticker not in watchlist_by_ticker:
            next_rank += 1
        watchlist_by_ticker[ticker] = {
            "ticker": ticker,
            "reason": "recorded fixture",
            "catalyst": "n/a",
            "rank": rank,
            "avg_volume_baseline": avg_volume_baseline,
        }
        recorded_any = True

    if not watchlist_by_ticker:
        print("No tickers recorded; not writing a watchlist file.")
        return 1
    if not recorded_any:
        print("No new tickers recorded this run; leaving existing watchlist file untouched.")
        return 1

    merged = sorted(watchlist_by_ticker.values(), key=lambda r: r["rank"])
    watchlist_path.write_text(json.dumps(merged, indent=2), encoding="utf-8")
    print(f"Wrote watchlist ({len(merged)} ticker(s), merged with any existing entries) -> {watchlist_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
