from datetime import datetime, timezone

import responses

from bot.config import Config
from bot.news.providers.alpaca import ALPACA_NEWS_URL, AlpacaNewsProvider
from bot.news.providers.benzinga import BENZINGA_NEWS_URL, BenzingaNewsProvider
from bot.news.providers.finnhub import FINNHUB_NEWS_URL, FinnhubNewsProvider
from bot.news.providers.newsapi import NEWSAPI_URL, NewsAPIProvider

SINCE = datetime(2024, 1, 1, tzinfo=timezone.utc)
SYMBOLS = ["AAPL", "TSLA"]


# ---------------------------------------------------------------------------
# Alpaca
# ---------------------------------------------------------------------------

@responses.activate
def test_alpaca_fetch_returns_articles():
    responses.add(
        responses.GET,
        ALPACA_NEWS_URL,
        json={
            "news": [{
                "headline": "Apple hits all-time high",
                "summary": "AAPL surged today.",
                "source": "Bloomberg",
                "url": "https://example.com/aapl",
                "updated_at": "2024-01-02T10:00:00Z",
                "symbols": ["AAPL"],
            }]
        },
        status=200,
    )
    provider = AlpacaNewsProvider("key", "secret")
    articles = provider.fetch(SYMBOLS, SINCE)
    assert len(articles) == 1
    assert articles[0].headline == "Apple hits all-time high"
    assert articles[0].symbol == "AAPL"
    assert articles[0].source == "Bloomberg"


@responses.activate
def test_alpaca_filters_out_unrelated_symbols():
    responses.add(
        responses.GET,
        ALPACA_NEWS_URL,
        json={
            "news": [{
                "headline": "NVDA news",
                "summary": "",
                "source": "Reuters",
                "url": "https://example.com/nvda",
                "updated_at": "2024-01-02T10:00:00Z",
                "symbols": ["NVDA"],
            }]
        },
        status=200,
    )
    provider = AlpacaNewsProvider("key", "secret")
    articles = provider.fetch(SYMBOLS, SINCE)
    assert articles == []


@responses.activate
def test_alpaca_graceful_on_http_error():
    responses.add(responses.GET, ALPACA_NEWS_URL, status=500)
    provider = AlpacaNewsProvider("key", "secret")
    articles = provider.fetch(SYMBOLS, SINCE)
    assert articles == []


def test_alpaca_from_config_missing_keys():
    cfg = Config(alpaca_api_key="", alpaca_secret_key="")
    assert AlpacaNewsProvider.from_config(cfg) is None


def test_alpaca_from_config_with_keys():
    cfg = Config(alpaca_api_key="k", alpaca_secret_key="s")
    provider = AlpacaNewsProvider.from_config(cfg)
    assert provider is not None
    assert provider.name == "alpaca"


# ---------------------------------------------------------------------------
# Finnhub
# ---------------------------------------------------------------------------

@responses.activate
def test_finnhub_fetch_returns_articles():
    responses.add(
        responses.GET,
        FINNHUB_NEWS_URL,
        json=[{
            "headline": "Tesla earnings beat expectations",
            "summary": "TSLA Q4 earnings were strong.",
            "source": "Reuters",
            "url": "https://example.com/tsla",
            "datetime": 1704150000,
        }],
        status=200,
    )
    provider = FinnhubNewsProvider("fh_key")
    articles = provider.fetch(["TSLA"], SINCE)
    assert len(articles) == 1
    assert articles[0].symbol == "TSLA"
    assert articles[0].headline == "Tesla earnings beat expectations"


@responses.activate
def test_finnhub_graceful_on_http_error():
    responses.add(responses.GET, FINNHUB_NEWS_URL, status=403)
    provider = FinnhubNewsProvider("bad_key")
    articles = provider.fetch(["AAPL"], SINCE)
    assert articles == []


def test_finnhub_from_config_missing_key():
    cfg = Config(alpaca_api_key="k", alpaca_secret_key="s", finnhub_api_key=None)
    assert FinnhubNewsProvider.from_config(cfg) is None


def test_finnhub_from_config_with_key():
    cfg = Config(alpaca_api_key="k", alpaca_secret_key="s", finnhub_api_key="fh_key")
    provider = FinnhubNewsProvider.from_config(cfg)
    assert provider is not None
    assert provider.name == "finnhub"


# ---------------------------------------------------------------------------
# NewsAPI
# ---------------------------------------------------------------------------

@responses.activate
def test_newsapi_fetch_returns_articles():
    responses.add(
        responses.GET,
        NEWSAPI_URL,
        json={
            "status": "ok",
            "articles": [{
                "title": "Apple launches new product",
                "description": "A new device was unveiled.",
                "source": {"name": "TechCrunch"},
                "url": "https://example.com/apple",
                "publishedAt": "2024-01-02T10:00:00Z",
            }],
        },
        status=200,
    )
    provider = NewsAPIProvider("na_key")
    articles = provider.fetch(["AAPL"], SINCE)
    assert len(articles) == 1
    assert articles[0].headline == "Apple launches new product"
    assert articles[0].source == "TechCrunch"


@responses.activate
def test_newsapi_graceful_on_http_error():
    responses.add(responses.GET, NEWSAPI_URL, status=429)
    provider = NewsAPIProvider("na_key")
    articles = provider.fetch(["AAPL"], SINCE)
    assert articles == []


def test_newsapi_from_config_missing_key():
    cfg = Config(alpaca_api_key="k", alpaca_secret_key="s", newsapi_key=None)
    assert NewsAPIProvider.from_config(cfg) is None


def test_newsapi_from_config_with_key():
    cfg = Config(alpaca_api_key="k", alpaca_secret_key="s", newsapi_key="na_key")
    provider = NewsAPIProvider.from_config(cfg)
    assert provider is not None
    assert provider.name == "newsapi"


# ---------------------------------------------------------------------------
# Benzinga
# ---------------------------------------------------------------------------

@responses.activate
def test_benzinga_fetch_returns_articles():
    responses.add(
        responses.GET,
        BENZINGA_NEWS_URL,
        json=[{
            "title": "AAPL stock rises",
            "teaser": "Apple shares up 3%.",
            "source": {"name": "Benzinga"},
            "url": "https://example.com/bz",
            "created": "Tue, 02 Jan 2024 10:00:00 +0000",
            "stocks": [{"name": "AAPL"}],
        }],
        status=200,
    )
    provider = BenzingaNewsProvider("bz_key")
    articles = provider.fetch(["AAPL"], SINCE)
    assert len(articles) == 1
    assert articles[0].symbol == "AAPL"
    assert articles[0].headline == "AAPL stock rises"


@responses.activate
def test_benzinga_filters_out_unrelated_symbols():
    responses.add(
        responses.GET,
        BENZINGA_NEWS_URL,
        json=[{
            "title": "MSFT news",
            "teaser": "",
            "source": {"name": "Benzinga"},
            "url": "https://example.com/msft",
            "created": "Tue, 02 Jan 2024 10:00:00 +0000",
            "stocks": [{"name": "MSFT"}],
        }],
        status=200,
    )
    provider = BenzingaNewsProvider("bz_key")
    articles = provider.fetch(["AAPL"], SINCE)
    assert articles == []


@responses.activate
def test_benzinga_graceful_on_http_error():
    responses.add(responses.GET, BENZINGA_NEWS_URL, status=401)
    provider = BenzingaNewsProvider("bz_key")
    articles = provider.fetch(["AAPL"], SINCE)
    assert articles == []


def test_benzinga_from_config_missing_key():
    cfg = Config(alpaca_api_key="k", alpaca_secret_key="s", benzinga_api_key=None)
    assert BenzingaNewsProvider.from_config(cfg) is None


def test_benzinga_from_config_with_key():
    cfg = Config(alpaca_api_key="k", alpaca_secret_key="s", benzinga_api_key="bz_key")
    provider = BenzingaNewsProvider.from_config(cfg)
    assert provider is not None
    assert provider.name == "benzinga"
