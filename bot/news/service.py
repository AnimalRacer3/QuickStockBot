import logging
from datetime import datetime
from typing import List, Optional

from ..config import Config
from .aggregator import collect
from .models import TickerSentiment
from .providers.alpaca import AlpacaNewsProvider
from .providers.benzinga import BenzingaNewsProvider
from .providers.finnhub import FinnhubNewsProvider
from .providers.newsapi import NewsAPIProvider
from .sentiment import aggregate_sentiment, score_articles

logger = logging.getLogger(__name__)

_PROVIDER_CLASSES = [
    AlpacaNewsProvider,
    FinnhubNewsProvider,
    NewsAPIProvider,
    BenzingaNewsProvider,
]


def _build_providers(config: Config) -> list:
    providers = []
    for cls in _PROVIDER_CLASSES:
        provider = cls.from_config(config)
        if provider is not None:
            providers.append(provider)
    if not providers:
        raise RuntimeError("No news providers available — check your API keys")
    return providers


def get_news_with_sentiment(
    symbols: List[str],
    since: datetime,
    config: Optional[Config] = None,
) -> List[TickerSentiment]:
    if config is None:
        config = Config.from_env()

    providers = _build_providers(config)
    by_symbol = collect(providers, symbols, since)

    results: List[TickerSentiment] = []
    for symbol, articles in by_symbol.items():
        scored = score_articles(articles, config.finbert_model_path) if articles else []
        agg = aggregate_sentiment(scored)
        results.append(TickerSentiment(symbol=symbol, articles=scored, aggregate=agg))
    return results
