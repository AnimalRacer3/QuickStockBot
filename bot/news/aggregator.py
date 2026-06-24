import re
import logging
from datetime import datetime
from difflib import SequenceMatcher
from typing import List

from .models import Article
from .providers.base import NewsProvider

logger = logging.getLogger(__name__)

_PUNCT_RE = re.compile(r"[^\w\s]")


def _normalize(headline: str) -> str:
    return _PUNCT_RE.sub("", headline.lower()).strip()


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def deduplicate(articles: List[Article], threshold: float = 0.85) -> List[Article]:
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
    providers: List[NewsProvider],
    symbols: List[str],
    since: datetime,
) -> dict[str, List[Article]]:
    all_articles: List[Article] = []
    for provider in providers:
        try:
            fetched = provider.fetch(symbols, since)
            logger.info("Provider %s returned %d articles", provider.name, len(fetched))
            all_articles.extend(fetched)
        except Exception as exc:
            logger.error("Provider %s raised an unexpected error: %s", provider.name, exc)

    deduped = deduplicate(all_articles)
    logger.info("After dedup: %d articles (from %d raw)", len(deduped), len(all_articles))

    by_symbol: dict[str, List[Article]] = {s: [] for s in symbols}
    for article in deduped:
        if article.symbol in by_symbol:
            by_symbol[article.symbol].append(article)
    return by_symbol
