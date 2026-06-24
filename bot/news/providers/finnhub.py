import logging
from datetime import datetime, timezone
from typing import Optional

import requests

from ..models import Article
from .base import NewsProvider

logger = logging.getLogger(__name__)

FINNHUB_NEWS_URL = "https://finnhub.io/api/v1/company-news"


class FinnhubNewsProvider(NewsProvider):
    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    @property
    def name(self) -> str:
        return "finnhub"

    def fetch(self, symbols: list[str], since: datetime) -> list[Article]:
        articles: list[Article] = []
        today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
        for symbol in symbols:
            try:
                params = {
                    "symbol": symbol,
                    "from": since.strftime("%Y-%m-%d"),
                    "to": today,
                    "token": self._api_key,
                }
                resp = requests.get(FINNHUB_NEWS_URL, params=params, timeout=10)
                resp.raise_for_status()
                for item in resp.json():
                    published = datetime.fromtimestamp(item.get("datetime", 0), tz=timezone.utc)
                    articles.append(Article(
                        symbol=symbol,
                        headline=item.get("headline", ""),
                        summary=item.get("summary", ""),
                        source=item.get("source", "finnhub"),
                        url=item.get("url", ""),
                        published_at=published,
                    ))
            except Exception as exc:
                logger.error("Finnhub news fetch failed for %s: %s", symbol, exc)
        return articles

    @classmethod
    def from_config(cls, config) -> Optional["FinnhubNewsProvider"]:
        if not config.finnhub_api_key:
            logger.warning("Skipping Finnhub provider: FINNHUB_API_KEY not set")
            return None
        return cls(config.finnhub_api_key)
