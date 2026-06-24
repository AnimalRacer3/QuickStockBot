from __future__ import annotations

import logging
import re
from datetime import datetime
from difflib import SequenceMatcher

from bot.news.models import Article
from bot.news.providers.base import NewsProvider

logger = logging.getLogger(__name__)

_PUNCT_RE = re.compile(r"[^\w\s]")


def _normalize(headline: str) -> str:
    return _PUNCT_RE.sub("", headline.lower()).strip()


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def deduplicate(articles: list[Article], threshold: float = 0.85) -> list[Article]:
    seen: list[str] = []
    result: list[Article] = []
    for article in articles:
        norm = _normalize(article.headline)
        if not norm:
            continue
        if any(_similarity(norm, s) >= threshold for s in seen):
            continue
        seen.append(norm)
        result.append(article)
    return result


def collect(
    providers: list[NewsProvider],
    symbols: list[str],
    since: datetime,
) -> dict[str, list[Article]]:
    all_articles: list[Article] = []
    for provider in providers:
        try:
            fetched = provider.fetch(symbols, since)
            logger.info("Provider %s returned %d articles", provider.name, len(fetched))
            all_articles.extend(fetched)
        except Exception as exc:
            logger.error("Provider %s raised: %s", provider.name, exc)

    deduped = deduplicate(all_articles)
    logger.info(
        "After dedup: %d articles (from %d raw)", len(deduped), len(all_articles)
    )

    by_symbol: dict[str, list[Article]] = {s: [] for s in symbols}
    for article in deduped:
        if article.symbol in by_symbol:
            by_symbol[article.symbol].append(article)
    return by_symbol
