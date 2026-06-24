from __future__ import annotations

from datetime import datetime, timezone

import httpx
import respx

from bot.alpaca.client import AlpacaClient
from bot.alpaca.config import AlpacaConfig
from bot.news.config import NewsConfig
from bot.news.providers.alpaca import AlpacaNewsProvider
from bot.news.providers.benzinga import BENZINGA_NEWS_URL, BenzingaNewsProvider
from bot.news.providers.finnhub import FINNHUB_NEWS_URL, FinnhubNewsProvider
from bot.news.providers.newsapi import NEWSAPI_URL, NewsAPIProvider

SINCE = datetime(2024, 1, 1, tzinfo=timezone.utc)
SYMBOLS = ["AAPL", "TSLA"]

_ALPACA_DATA_URL = "https://data.alpaca.markets"
_ALPACA_NEWS_URL = f"{_ALPACA_DATA_URL}/v1beta1/news"

_ALPACA_CFG = AlpacaConfig(
    api_key="test-key",
    secret_key="test-secret",
    base_url="https://paper-api.alpaca.markets",
    data_url=_ALPACA_DATA_URL,
)


def _make_alpaca_provider() -> AlpacaNewsProvider:
    http = httpx.Client(
        headers={
            "APCA-API-KEY-ID": _ALPACA_CFG.api_key,
            "APCA-API-SECRET-KEY": _ALPACA_CFG.secret_key,
        }
    )
    return AlpacaNewsProvider(AlpacaClient(config=_ALPACA_CFG, http_client=http))


# ---------------------------------------------------------------------------
# Alpaca
# ---------------------------------------------------------------------------


@respx.mock
def test_alpaca_fetch_returns_articles() -> None:
    respx.get(_ALPACA_NEWS_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "news": [
                    {
                        "headline": "Apple hits all-time high",
                        "summary": "AAPL surged today.",
                        "source": "Bloomberg",
                        "url": "https://example.com/aapl",
                        "updated_at": "2024-01-02T10:00:00Z",
                        "symbols": ["AAPL"],
                    }
                ]
            },
        )
    )
    articles = _make_alpaca_provider().fetch(SYMBOLS, SINCE)
    assert len(articles) == 1
    assert articles[0].headline == "Apple hits all-time high"
    assert articles[0].symbol == "AAPL"
    assert articles[0].source == "Bloomberg"


@respx.mock
def test_alpaca_filters_out_unrelated_symbols() -> None:
    respx.get(_ALPACA_NEWS_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "news": [
                    {
                        "headline": "NVDA rally",
                        "summary": "",
                        "source": "Reuters",
                        "url": "https://example.com/nvda",
                        "updated_at": "2024-01-02T10:00:00Z",
                        "symbols": ["NVDA"],
                    }
                ]
            },
        )
    )
    assert _make_alpaca_provider().fetch(SYMBOLS, SINCE) == []


@respx.mock
def test_alpaca_graceful_on_http_error() -> None:
    respx.get(_ALPACA_NEWS_URL).mock(return_value=httpx.Response(500))
    assert _make_alpaca_provider().fetch(SYMBOLS, SINCE) == []


def test_alpaca_from_alpaca_config_missing_keys() -> None:
    bad = AlpacaConfig(
        api_key="",
        secret_key="",
        base_url="https://paper-api.alpaca.markets",
    )
    assert AlpacaNewsProvider.from_alpaca_config(bad) is None


def test_alpaca_from_alpaca_config_with_keys() -> None:
    provider = AlpacaNewsProvider.from_alpaca_config(_ALPACA_CFG)
    assert provider is not None
    assert provider.name == "alpaca"


# ---------------------------------------------------------------------------
# Finnhub
# ---------------------------------------------------------------------------


@respx.mock
def test_finnhub_fetch_returns_articles() -> None:
    respx.get(FINNHUB_NEWS_URL).mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "headline": "Tesla earnings beat",
                    "summary": "TSLA Q4 strong.",
                    "source": "Reuters",
                    "url": "https://example.com/tsla",
                    "datetime": 1704150000,
                }
            ],
        )
    )
    provider = FinnhubNewsProvider("fh_key")
    articles = provider.fetch(["TSLA"], SINCE)
    assert len(articles) == 1
    assert articles[0].symbol == "TSLA"
    assert articles[0].headline == "Tesla earnings beat"


@respx.mock
def test_finnhub_graceful_on_http_error() -> None:
    respx.get(FINNHUB_NEWS_URL).mock(return_value=httpx.Response(403))
    assert FinnhubNewsProvider("bad_key").fetch(["AAPL"], SINCE) == []


def test_finnhub_from_config_missing_key() -> None:
    cfg = NewsConfig(finnhub_api_key=None)
    assert FinnhubNewsProvider.from_config(cfg) is None


def test_finnhub_from_config_with_key() -> None:
    cfg = NewsConfig(finnhub_api_key="fh_key")
    provider = FinnhubNewsProvider.from_config(cfg)
    assert provider is not None
    assert provider.name == "finnhub"


# ---------------------------------------------------------------------------
# NewsAPI
# ---------------------------------------------------------------------------


@respx.mock
def test_newsapi_fetch_returns_articles() -> None:
    respx.get(NEWSAPI_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "status": "ok",
                "articles": [
                    {
                        "title": "Apple launches new product",
                        "description": "A new device.",
                        "source": {"name": "TechCrunch"},
                        "url": "https://example.com/apple",
                        "publishedAt": "2024-01-02T10:00:00Z",
                    }
                ],
            },
        )
    )
    provider = NewsAPIProvider("na_key")
    articles = provider.fetch(["AAPL"], SINCE)
    assert len(articles) == 1
    assert articles[0].headline == "Apple launches new product"
    assert articles[0].source == "TechCrunch"


@respx.mock
def test_newsapi_graceful_on_http_error() -> None:
    respx.get(NEWSAPI_URL).mock(return_value=httpx.Response(429))
    assert NewsAPIProvider("na_key").fetch(["AAPL"], SINCE) == []


def test_newsapi_from_config_missing_key() -> None:
    cfg = NewsConfig(newsapi_key=None)
    assert NewsAPIProvider.from_config(cfg) is None


def test_newsapi_from_config_with_key() -> None:
    cfg = NewsConfig(newsapi_key="na_key")
    provider = NewsAPIProvider.from_config(cfg)
    assert provider is not None
    assert provider.name == "newsapi"


# ---------------------------------------------------------------------------
# Benzinga
# ---------------------------------------------------------------------------


@respx.mock
def test_benzinga_fetch_returns_articles() -> None:
    respx.get(BENZINGA_NEWS_URL).mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "title": "AAPL stock rises",
                    "teaser": "Apple shares up 3%.",
                    "source": {"name": "Benzinga"},
                    "url": "https://example.com/bz",
                    "created": "Tue, 02 Jan 2024 10:00:00 +0000",
                    "stocks": [{"name": "AAPL"}],
                }
            ],
        )
    )
    provider = BenzingaNewsProvider("bz_key")
    articles = provider.fetch(["AAPL"], SINCE)
    assert len(articles) == 1
    assert articles[0].symbol == "AAPL"
    assert articles[0].headline == "AAPL stock rises"


@respx.mock
def test_benzinga_filters_out_unrelated_symbols() -> None:
    respx.get(BENZINGA_NEWS_URL).mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "title": "MSFT news",
                    "teaser": "",
                    "source": {"name": "Benzinga"},
                    "url": "https://example.com/msft",
                    "created": "Tue, 02 Jan 2024 10:00:00 +0000",
                    "stocks": [{"name": "MSFT"}],
                }
            ],
        )
    )
    assert BenzingaNewsProvider("bz_key").fetch(["AAPL"], SINCE) == []


@respx.mock
def test_benzinga_graceful_on_http_error() -> None:
    respx.get(BENZINGA_NEWS_URL).mock(return_value=httpx.Response(401))
    assert BenzingaNewsProvider("bz_key").fetch(["AAPL"], SINCE) == []


def test_benzinga_from_config_missing_key() -> None:
    cfg = NewsConfig(benzinga_api_key=None)
    assert BenzingaNewsProvider.from_config(cfg) is None


def test_benzinga_from_config_with_key() -> None:
    cfg = NewsConfig(benzinga_api_key="bz_key")
    provider = BenzingaNewsProvider.from_config(cfg)
    assert provider is not None
    assert provider.name == "benzinga"
