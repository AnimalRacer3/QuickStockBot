from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from bot.news.models import Article, ArticleWithSentiment, SentimentScore
from bot.news.sentiment import aggregate_sentiment, score_articles

_PUB = datetime(2024, 1, 2, tzinfo=timezone.utc)


def _article(headline: str, summary: str = "") -> Article:
    return Article(
        symbol="AAPL",
        headline=headline,
        summary=summary,
        source="test",
        url="https://example.com",
        published_at=_PUB,
    )


def _scored(label: str, pos: float, neg: float, neu: float) -> ArticleWithSentiment:
    return ArticleWithSentiment(
        article=_article("irrelevant"),
        sentiment=SentimentScore(positive=pos, negative=neg, neutral=neu, score=pos - neg, label=label),
    )


# ---------------------------------------------------------------------------
# Unit tests (no model required)
# ---------------------------------------------------------------------------

def _mock_pipe_returning(label: str, pos: float, neg: float, neu: float):
    pipe = MagicMock()
    pipe.return_value = [[
        {"label": "positive", "score": pos},
        {"label": "negative", "score": neg},
        {"label": "neutral", "score": neu},
    ]]
    return pipe


def test_score_articles_positive_mock():
    pipe = _mock_pipe_returning("positive", pos=0.85, neg=0.05, neu=0.10)
    with patch("bot.news.sentiment._get_pipeline", return_value=pipe):
        scored = score_articles([_article("Record profits and raised guidance")])
    assert scored[0].sentiment.label == "positive"
    assert scored[0].sentiment.positive == pytest.approx(0.85)
    assert scored[0].sentiment.score == pytest.approx(0.80)


def test_score_articles_negative_mock():
    pipe = _mock_pipe_returning("negative", pos=0.05, neg=0.90, neu=0.05)
    with patch("bot.news.sentiment._get_pipeline", return_value=pipe):
        scored = score_articles([_article("Massive losses; company files for bankruptcy")])
    assert scored[0].sentiment.label == "negative"
    assert scored[0].sentiment.score < 0


def test_score_articles_uses_headline_and_summary():
    pipe = _mock_pipe_returning("neutral", pos=0.1, neg=0.1, neu=0.8)
    with patch("bot.news.sentiment._get_pipeline", return_value=pipe):
        score_articles([_article("headline", "summary text")])
    call_text = pipe.call_args[0][0]
    assert "headline" in call_text
    assert "summary text" in call_text


def test_score_articles_headline_only_when_no_summary():
    pipe = _mock_pipe_returning("neutral", pos=0.1, neg=0.1, neu=0.8)
    with patch("bot.news.sentiment._get_pipeline", return_value=pipe):
        score_articles([_article("headline only", summary="")])
    call_text = pipe.call_args[0][0]
    assert call_text == "headline only"


def test_score_articles_empty_list():
    pipe = MagicMock()
    with patch("bot.news.sentiment._get_pipeline", return_value=pipe):
        result = score_articles([])
    assert result == []
    pipe.assert_not_called()


# ---------------------------------------------------------------------------
# aggregate_sentiment
# ---------------------------------------------------------------------------

def test_aggregate_positive():
    scored = [_scored("positive", 0.8, 0.1, 0.1), _scored("positive", 0.7, 0.2, 0.1)]
    agg = aggregate_sentiment(scored)
    assert agg.label == "positive"
    assert agg.positive > agg.negative
    assert agg.score > 0


def test_aggregate_negative():
    scored = [_scored("negative", 0.05, 0.90, 0.05), _scored("negative", 0.10, 0.85, 0.05)]
    agg = aggregate_sentiment(scored)
    assert agg.label == "negative"
    assert agg.score < 0


def test_aggregate_neutral():
    scored = [_scored("neutral", 0.1, 0.1, 0.8), _scored("neutral", 0.15, 0.15, 0.70)]
    agg = aggregate_sentiment(scored)
    assert agg.label == "neutral"


def test_aggregate_empty_returns_neutral():
    agg = aggregate_sentiment([])
    assert agg.label == "neutral"
    assert agg.score == 0.0
    assert agg.neutral == 1.0


def test_aggregate_averages_correctly():
    scored = [_scored("positive", 0.6, 0.2, 0.2), _scored("negative", 0.2, 0.6, 0.2)]
    agg = aggregate_sentiment(scored)
    assert agg.positive == pytest.approx(0.4)
    assert agg.negative == pytest.approx(0.4)
    assert agg.score == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# FinBERT smoke tests (require model download — mark with -m finbert to run)
# ---------------------------------------------------------------------------

@pytest.mark.finbert
def test_finbert_positive_sentence():
    articles = [_article("Company reports record profits and raises full-year guidance")]
    scored = score_articles(articles)
    assert scored[0].sentiment.label == "positive"


@pytest.mark.finbert
def test_finbert_negative_sentence():
    articles = [_article("Company files for bankruptcy amid massive losses and fraud allegations")]
    scored = score_articles(articles)
    assert scored[0].sentiment.label == "negative"
