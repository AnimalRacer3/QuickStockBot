import os
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class Config:
    alpaca_api_key: str
    alpaca_secret_key: str
    finnhub_api_key: Optional[str] = None
    newsapi_key: Optional[str] = None
    benzinga_api_key: Optional[str] = None
    finbert_model_path: str = "ProsusAI/finbert"

    @classmethod
    def from_env(cls) -> "Config":
        alpaca_key = os.environ.get("ALPACA_API_KEY", "")
        alpaca_secret = os.environ.get("ALPACA_SECRET_KEY", "")
        if not alpaca_key or not alpaca_secret:
            logger.warning("ALPACA_API_KEY or ALPACA_SECRET_KEY not set")
        return cls(
            alpaca_api_key=alpaca_key,
            alpaca_secret_key=alpaca_secret,
            finnhub_api_key=os.environ.get("FINNHUB_API_KEY"),
            newsapi_key=os.environ.get("NEWSAPI_KEY"),
            benzinga_api_key=os.environ.get("BENZINGA_API_KEY"),
            finbert_model_path=os.environ.get("FINBERT_MODEL_PATH", "ProsusAI/finbert"),
        )
