#!/usr/bin/env python3
"""Manual verification script: fetches real news + FinBERT sentiment for a few tickers.

Usage:
    ALPACA_API_KEY=... ALPACA_SECRET_KEY=... FINNHUB_API_KEY=... \
        python scripts/verify_news.py
"""
import logging
import sys
import os
from datetime import datetime, timedelta, timezone

# Allow running from project root without installing the package
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

from bot.config import Config
from bot.news.service import get_news_with_sentiment

SYMBOLS = ["AAPL", "TSLA", "MSFT"]
LOOKBACK_DAYS = 7

if __name__ == "__main__":
    config = Config.from_env()
    since = datetime.now(tz=timezone.utc) - timedelta(days=LOOKBACK_DAYS)

    print(f"Fetching news for {SYMBOLS} since {since.date()} ...\n")
    results = get_news_with_sentiment(SYMBOLS, since, config)

    for ticker in results:
        agg = ticker.aggregate
        print(f"{'=' * 60}")
        print(f"  {ticker.symbol}  |  {agg.label.upper()}  (score={agg.score:+.3f})")
        print(f"  pos={agg.positive:.3f}  neg={agg.negative:.3f}  neu={agg.neutral:.3f}")
        print(f"  Articles: {len(ticker.articles)}")
        for aw in ticker.articles[:5]:
            a = aw.article
            s = aw.sentiment
            label_tag = f"[{s.label:8s}]"
            print(f"    {label_tag} {a.headline[:72]}")
            print(f"              source={a.source}  date={a.published_at.date()}")
    print(f"{'=' * 60}")
