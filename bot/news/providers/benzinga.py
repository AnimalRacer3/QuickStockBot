import logging
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Optional

import requests

from ..models import Article
from .base import NewsProvider

logger = logging.getLogger(__name__)

BENZINGA_NEWS_URL = "https://api.benzinga.com/api/v2/news"


class BenzingaNewsProvider(NewsProvider):
    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    @property
    def name(self) -> str:
        return "benzinga"

    def fetch(self, symbols: list[str], since: datetime) -> list[Article]:
        articles: list[Article] = []
        try:
            params = {
                "tickers": ",".join(symbols),
                "dateFrom": since.strftime("%Y-%m-%d"),
                "dateTo": datetime.now(tz=timezone.utc).strftime("%Y-%m-%d"),
                "token": self._api_key,
                "pageSize": 50,
            }
            resp = requests.get(BENZINGA_NEWS_URL, params=params, timeout=10)
            resp.raise_for_status()
            for item in resp.json():
                for stock in item.get("stocks", []):
                    sym = stock.get("name", "")
                    if sym not in symbols:
                        continue
                    published = _parse_date(item.get("created", ""))
                    source = item.get("source", {})
                    source_name = source.get("name", "benzinga") if isinstance(source, dict) else str(source)
                    articles.append(Article(
                        symbol=sym,
                        headline=item.get("title", ""),
                        summary=item.get("teaser", "") or "",
                        source=source_name,
                        url=item.get("url", ""),
                        published_at=published,
                    ))
        except Exception as exc:
            logger.error("Benzinga news fetch failed: %s", exc)
        return articles

    @classmethod
    def from_config(cls, config) -> Optional["BenzingaNewsProvider"]:
        if not config.benzinga_api_key:
            logger.warning("Skipping Benzinga provider: BENZINGA_API_KEY not set")
            return None
        return cls(config.benzinga_api_key)


def _parse_date(date_str: str) -> datetime:
    if not date_str:
        return datetime.now(tz=timezone.utc)
    try:
        return parsedate_to_datetime(date_str)
    except Exception:
        pass
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except Exception:
        return datetime.now(tz=timezone.utc)
