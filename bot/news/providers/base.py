from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from ..models import Article


class NewsProvider(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def fetch(self, symbols: list[str], since: datetime) -> list[Article]: ...

    @classmethod
    @abstractmethod
    def from_config(cls, config) -> Optional["NewsProvider"]: ...
