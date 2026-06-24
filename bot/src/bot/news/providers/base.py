from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from bot.news.models import Article


class NewsProvider(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def fetch(self, symbols: list[str], since: datetime) -> list[Article]: ...
