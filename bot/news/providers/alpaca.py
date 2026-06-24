import logging
from datetime import datetime, timezone
from typing import Optional

import requests

from ..models import Article
from .base import NewsProvider

logger = logging.getLogger(__name__)

ALPACA_NEWS_URL = "https://data.alpaca.markets/v1beta1/news"


class AlpacaNewsProvider(NewsProvider):
    def __init__(self, api_key: str, secret_key: str) -> None:
        self._headers = {
            "APCA-API-KEY-ID": api_key,
            "APCA-API-SECRET-KEY": secret_key,
        }

    @property
    def name(self) -> str:
        return "alpaca"

    def fetch(self, symbols: list[str], since: datetime) -> list[Article]:
        articles: list[Article] = []
        try:
            params = {
                "symbols": ",".join(symbols),
                "start": since.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "limit": 50,
                "sort": "desc",
            }
            resp = requests.get(ALPACA_NEWS_URL, headers=self._headers, params=params, timeout=10)
            resp.raise_for_status()
            for item in resp.json().get("news", []):
                for sym in item.get("symbols", []):
                    if sym not in symbols:
                        continue
                    published = datetime.fromisoformat(
                        item["updated_at"].replace("Z", "+00:00")
                    )
                    articles.append(Article(
                        symbol=sym,
                        headline=item.get("headline", ""),
                        summary=item.get("summary", ""),
                        source=item.get("source", "alpaca"),
                        url=item.get("url", ""),
                        published_at=published,
                    ))
        except Exception as exc:
            logger.error("Alpaca news fetch failed: %s", exc)
        return articles

    @classmethod
    def from_config(cls, config) -> Optional["AlpacaNewsProvider"]:
        if not config.alpaca_api_key or not config.alpaca_secret_key:
            logger.warning("Skipping Alpaca provider: missing API keys")
            return None
        return cls(config.alpaca_api_key, config.alpaca_secret_key)
