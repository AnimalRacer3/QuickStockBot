import logging
from datetime import datetime, timezone
from typing import Optional

import requests

from ..models import Article
from .base import NewsProvider

logger = logging.getLogger(__name__)

NEWSAPI_URL = "https://newsapi.org/v2/everything"


class NewsAPIProvider(NewsProvider):
    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    @property
    def name(self) -> str:
        return "newsapi"

    def fetch(self, symbols: list[str], since: datetime) -> list[Article]:
        articles: list[Article] = []
        for symbol in symbols:
            try:
                params = {
                    "q": symbol,
                    "from": since.strftime("%Y-%m-%dT%H:%M:%S"),
                    "sortBy": "publishedAt",
                    "apiKey": self._api_key,
                    "language": "en",
                    "pageSize": 20,
                }
                resp = requests.get(NEWSAPI_URL, params=params, timeout=10)
                resp.raise_for_status()
                for item in resp.json().get("articles", []):
                    published_str = item.get("publishedAt", "")
                    try:
                        published = datetime.fromisoformat(published_str.replace("Z", "+00:00"))
                    except (ValueError, AttributeError):
                        published = datetime.now(tz=timezone.utc)
                    articles.append(Article(
                        symbol=symbol,
                        headline=item.get("title", ""),
                        summary=item.get("description", "") or "",
                        source=(item.get("source") or {}).get("name", "newsapi"),
                        url=item.get("url", ""),
                        published_at=published,
                    ))
            except Exception as exc:
                logger.error("NewsAPI fetch failed for %s: %s", symbol, exc)
        return articles

    @classmethod
    def from_config(cls, config) -> Optional["NewsAPIProvider"]:
        if not config.newsapi_key:
            logger.warning("Skipping NewsAPI provider: NEWSAPI_KEY not set")
            return None
        return cls(config.newsapi_key)
