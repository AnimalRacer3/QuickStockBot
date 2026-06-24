from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

import httpx

from bot.news.config import NewsConfig
from bot.news.models import Article
from bot.news.providers.base import NewsProvider

logger = logging.getLogger(__name__)

FINNHUB_NEWS_URL = "https://finnhub.io/api/v1/company-news"


class FinnhubNewsProvider(NewsProvider):
    def __init__(self, api_key: str, http_client: Optional[httpx.Client] = None) -> None:
        self._api_key = api_key
        self._http = http_client or httpx.Client(timeout=10.0)

    @property
    def name(self) -> str:
        return "finnhub"

    def fetch(self, symbols: list[str], since: datetime) -> list[Article]:
        articles: list[Article] = []
        today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
        for symbol in symbols:
            try:
                resp = self._http.get(
                    FINNHUB_NEWS_URL,
                    params={
                        "symbol": symbol,
                        "from": since.strftime("%Y-%m-%d"),
                        "to": today,
                        "token": self._api_key,
                    },
                )
                resp.raise_for_status()
                for item in resp.json():
                    published = datetime.fromtimestamp(
                        item.get("datetime", 0), tz=timezone.utc
                    )
                    articles.append(
                        Article(
                            symbol=symbol,
                            headline=item.get("headline", ""),
                            summary=item.get("summary", ""),
                            source=item.get("source", "finnhub"),
                            url=item.get("url", ""),
                            published_at=published,
                        )
                    )
            except Exception as exc:
                logger.error("Finnhub fetch failed for %s: %s", symbol, exc)
        return articles

    @classmethod
    def from_config(cls, config: NewsConfig) -> Optional[FinnhubNewsProvider]:
        if not config.finnhub_api_key:
            logger.warning("Skipping Finnhub: FINNHUB_API_KEY not set")
            return None
        return cls(config.finnhub_api_key)
