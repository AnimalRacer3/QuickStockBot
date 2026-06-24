from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from bot.alpaca.client import AlpacaClient
from bot.alpaca.config import AlpacaConfig
from bot.news.aggregator import collect
from bot.news.config import NewsConfig
from bot.news.models import TickerSentiment
from bot.news.providers.alpaca import AlpacaNewsProvider
from bot.news.providers.base import NewsProvider
from bot.news.providers.benzinga import BenzingaNewsProvider
from bot.news.providers.finnhub import FinnhubNewsProvider
from bot.news.providers.newsapi import NewsAPIProvider
from bot.news.sentiment import aggregate_sentiment, score_articles

logger = logging.getLogger(__name__)


def _build_providers(
    alpaca_client: Optional[AlpacaClient],
    news_config: NewsConfig,
) -> list[NewsProvider]:
    providers: list[NewsProvider] = []

    if alpaca_client is not None:
        providers.append(AlpacaNewsProvider(alpaca_client))
    else:
        logger.warning("No Alpaca client provided — skipping Alpaca provider")

    for cls, key, label in [
        (FinnhubNewsProvider, news_config.finnhub_api_key, "FINNHUB_API_KEY"),
        (NewsAPIProvider, news_config.newsapi_key, "NEWSAPI_KEY"),
        (BenzingaNewsProvider, news_config.benzinga_api_key, "BENZINGA_API_KEY"),
    ]:
        if key:
            providers.append(cls(key))  # type: ignore[call-arg]
        else:
            logger.warning("Skipping %s: %s not set", cls.__name__, label)

    if not providers:
        raise RuntimeError("No news providers available — check your API keys")
    return providers


def get_news_with_sentiment(
    symbols: list[str],
    since: datetime,
    alpaca_client: Optional[AlpacaClient] = None,
    news_config: Optional[NewsConfig] = None,
) -> list[TickerSentiment]:
    if alpaca_client is None:
        alpaca_config = AlpacaConfig.from_env()
        alpaca_client = AlpacaClient(alpaca_config)

    if news_config is None:
        news_config = NewsConfig.from_env()

    providers = _build_providers(alpaca_client, news_config)
    by_symbol = collect(providers, symbols, since)

    results: list[TickerSentiment] = []
    for symbol, articles in by_symbol.items():
        scored = score_articles(articles, news_config.finbert_model_path) if articles else []
        agg = aggregate_sentiment(scored)
        results.append(TickerSentiment(symbol=symbol, articles=scored, aggregate=agg))
    return results
