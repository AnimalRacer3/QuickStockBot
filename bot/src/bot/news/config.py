from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class NewsConfig:
    finnhub_api_key: Optional[str] = None
    newsapi_key: Optional[str] = None
    benzinga_api_key: Optional[str] = None
    finbert_model_path: str = "ProsusAI/finbert"

    @classmethod
    def from_env(cls) -> NewsConfig:
        return cls(
            finnhub_api_key=os.environ.get("FINNHUB_API_KEY"),
            newsapi_key=os.environ.get("NEWSAPI_KEY"),
            benzinga_api_key=os.environ.get("BENZINGA_API_KEY"),
            finbert_model_path=os.environ.get("FINBERT_MODEL_PATH", "ProsusAI/finbert"),
        )
