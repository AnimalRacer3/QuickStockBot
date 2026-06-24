from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from bot.alpaca.client import AlpacaClient
from bot.alpaca.config import AlpacaConfig
from bot.news.models import Article
from bot.news.providers.base import NewsProvider

logger = logging.getLogger(__name__)

_NEWS_PATH = "/v1beta1/news"


class AlpacaNewsProvider(NewsProvider):
    """Reuses Section 1's AlpacaClient for auth, retry logic, and httpx transport."""

    def __init__(self, client: AlpacaClient) -> None:
        self._client = client

    @property
    def name(self) -> str:
        return "alpaca"

    def fetch(self, symbols: list[str], since: datetime) -> list[Article]:
        articles: list[Article] = []
        try:
            data = self._client._data_get(
                _NEWS_PATH,
                symbols=",".join(symbols),
                start=since.isoformat(),
                limit=50,
                sort="desc",
            )
            for item in data.get("news", []):
                for sym in item.get("symbols", []):
                    if sym not in symbols:
                        continue
                    articles.append(
                        Article(
                            symbol=sym,
                            headline=item.get("headline", ""),
                            summary=item.get("summary", ""),
                            source=item.get("source", "alpaca"),
                            url=item.get("url", ""),
                            published_at=item["updated_at"],
                        )
                    )
        except Exception as exc:
            logger.error("Alpaca news fetch failed: %s", exc)
        return articles

    @classmethod
    def from_alpaca_config(cls, config: AlpacaConfig) -> Optional[AlpacaNewsProvider]:
        if not config.api_key or not config.secret_key:
            logger.warning("Skipping Alpaca provider: missing API keys")
            return None
        return cls(AlpacaClient(config))
