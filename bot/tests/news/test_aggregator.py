from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

from bot.news.aggregator import collect, deduplicate
from bot.news.models import Article

SINCE = datetime(2024, 1, 1, tzinfo=timezone.utc)
_PUB = datetime(2024, 1, 2, tzinfo=timezone.utc)


def _article(headline: str, symbol: str = "AAPL") -> Article:
    return Article(
        symbol=symbol,
        headline=headline,
        summary="",
        source="test",
        url="https://example.com",
        published_at=_PUB,
    )


# ---------------------------------------------------------------------------
# deduplicate
# ---------------------------------------------------------------------------


def test_deduplicate_removes_exact_duplicate() -> None:
    articles = [
        _article("Apple stock surges after earnings beat"),
        _article("Apple stock surges after earnings beat"),
    ]
    assert len(deduplicate(articles)) == 1


def test_deduplicate_removes_fuzzy_duplicate() -> None:
    articles = [
        _article("Apple stock surges following strong earnings report"),
        _article("Apple stock surges following strong earnings"),
    ]
    assert len(deduplicate(articles)) == 1


def test_deduplicate_keeps_distinct_articles() -> None:
    articles = [
        _article("Apple stock surges after earnings beat"),
        _article("Tesla faces supply chain challenges in 2024"),
    ]
    assert len(deduplicate(articles)) == 2


def test_deduplicate_skips_empty_headlines() -> None:
    articles = [_article(""), _article("Apple earnings strong")]
    result = deduplicate(articles)
    assert len(result) == 1
    assert result[0].headline == "Apple earnings strong"


def test_deduplicate_custom_threshold() -> None:
    articles = [
        _article("Apple stock surges after earnings"),
        _article("Apple stock dips after earnings"),
    ]
    assert len(deduplicate(articles, threshold=0.99)) == 2
    assert len(deduplicate(articles, threshold=0.5)) == 1


def test_deduplicate_cross_provider_first_wins() -> None:
    articles = [
        Article(
            symbol="AAPL",
            headline="Apple hits record high",
            summary="",
            source="alpaca",
            url="https://a.com",
            published_at=_PUB,
        ),
        Article(
            symbol="AAPL",
            headline="Apple hits record high",
            summary="",
            source="finnhub",
            url="https://b.com",
            published_at=_PUB,
        ),
    ]
    result = deduplicate(articles)
    assert len(result) == 1
    assert result[0].source == "alpaca"


# ---------------------------------------------------------------------------
# collect
# ---------------------------------------------------------------------------


def test_collect_groups_articles_by_symbol() -> None:
    provider = MagicMock()
    provider.name = "mock"
    provider.fetch.return_value = [
        _article("AAPL news", "AAPL"),
        _article("TSLA news", "TSLA"),
    ]
    result = collect([provider], ["AAPL", "TSLA"], SINCE)
    assert len(result["AAPL"]) == 1
    assert len(result["TSLA"]) == 1


def test_collect_returns_empty_lists_when_no_news() -> None:
    provider = MagicMock()
    provider.name = "mock"
    provider.fetch.return_value = []
    result = collect([provider], ["AAPL", "TSLA"], SINCE)
    assert result["AAPL"] == []
    assert result["TSLA"] == []


def test_collect_deduplicates_across_providers() -> None:
    p1 = MagicMock()
    p1.name = "provider_a"
    p1.fetch.return_value = [_article("Breaking: Apple earnings beat", "AAPL")]

    p2 = MagicMock()
    p2.name = "provider_b"
    p2.fetch.return_value = [_article("Breaking: Apple earnings beat", "AAPL")]

    result = collect([p1, p2], ["AAPL"], SINCE)
    assert len(result["AAPL"]) == 1


def test_collect_continues_if_provider_raises() -> None:
    bad = MagicMock()
    bad.name = "bad"
    bad.fetch.side_effect = RuntimeError("network down")

    good = MagicMock()
    good.name = "good"
    good.fetch.return_value = [_article("AAPL up 5%", "AAPL")]

    result = collect([bad, good], ["AAPL"], SINCE)
    assert len(result["AAPL"]) == 1


def test_collect_ignores_articles_for_unknown_symbols() -> None:
    provider = MagicMock()
    provider.name = "mock"
    provider.fetch.return_value = [_article("NVDA news", "NVDA")]
    result = collect([provider], ["AAPL"], SINCE)
    assert result["AAPL"] == []
    assert "NVDA" not in result
