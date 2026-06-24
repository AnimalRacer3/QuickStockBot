#!/usr/bin/env python3
"""Manual verification script: real news + FinBERT sentiment for a few tickers.

Prerequisites:
    pip install transformers torch   # for FinBERT (not in project lockfile)

Usage (from repo root):
    cd bot
    ALPACA_API_KEY=... ALPACA_API_SECRET=... PAPER_TRADING=true \
    ALPACA_LIVE_CONFIRMED=true FINNHUB_API_KEY=... \
        uv run python ../scripts/verify_news.py
"""
from __future__ import annotations

import logging
import sys
from datetime import datetime, timedelta, timezone

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

from bot.alpaca.client import AlpacaClient  # noqa: E402
from bot.alpaca.config import AlpacaConfig  # noqa: E402
from bot.news.config import NewsConfig  # noqa: E402
from bot.news.service import get_news_with_sentiment  # noqa: E402

SYMBOLS = ["AAPL", "TSLA", "MSFT"]
LOOKBACK_DAYS = 7

if __name__ == "__main__":
    try:
        alpaca_config = AlpacaConfig.from_env()
    except EnvironmentError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    news_config = NewsConfig.from_env()
    alpaca_client = AlpacaClient(alpaca_config)
    since = datetime.now(tz=timezone.utc) - timedelta(days=LOOKBACK_DAYS)

    print(f"Fetching news for {SYMBOLS} since {since.date()} ...\n")
    results = get_news_with_sentiment(SYMBOLS, since, alpaca_client, news_config)

    for ticker in results:
        agg = ticker.aggregate
        print("=" * 60)
        print(f"  {ticker.symbol}  |  {agg.label.upper()}  (score={agg.score:+.3f})")
        print(f"  pos={agg.positive:.3f}  neg={agg.negative:.3f}  neu={agg.neutral:.3f}")
        print(f"  Articles: {len(ticker.articles)}")
        for aw in ticker.articles[:5]:
            a = aw.article
            s = aw.sentiment
            print(f"    [{s.label:8s}] {a.headline[:72]}")
            print(f"              source={a.source}  date={a.published_at.date()}")
    print("=" * 60)
