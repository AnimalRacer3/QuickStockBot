import logging
from typing import List

from .models import Article, ArticleWithSentiment, SentimentScore

logger = logging.getLogger(__name__)

# keyed by model_path so multiple paths can coexist in tests
_pipeline_cache: dict[str, object] = {}


def _get_pipeline(model_path: str):
    if model_path not in _pipeline_cache:
        from transformers import pipeline  # lazy import — heavy dependency

        logger.info("Loading FinBERT model from %s (one-time)", model_path)
        _pipeline_cache[model_path] = pipeline(
            "text-classification",
            model=model_path,
            top_k=None,
            truncation=True,
            max_length=512,
        )
    return _pipeline_cache[model_path]


def _score_text(pipe, text: str) -> SentimentScore:
    if not text:
        return SentimentScore(positive=0.0, negative=0.0, neutral=1.0, score=0.0, label="neutral")

    raw = pipe(text[:512])
    # pipeline with top_k=None returns [[{label, score}, ...]] for a single string
    items = raw[0] if raw and isinstance(raw[0], list) else raw
    scores = {r["label"].lower(): float(r["score"]) for r in items}

    pos = scores.get("positive", 0.0)
    neg = scores.get("negative", 0.0)
    neu = scores.get("neutral", 0.0)
    label = max(scores, key=scores.get)
    return SentimentScore(positive=pos, negative=neg, neutral=neu, score=pos - neg, label=label)


def score_articles(
    articles: List[Article],
    model_path: str = "ProsusAI/finbert",
) -> List[ArticleWithSentiment]:
    pipe = _get_pipeline(model_path)
    result: List[ArticleWithSentiment] = []
    for article in articles:
        text = f"{article.headline}. {article.summary}" if article.summary else article.headline
        sentiment = _score_text(pipe, text)
        result.append(ArticleWithSentiment(article=article, sentiment=sentiment))
    return result


def aggregate_sentiment(scored: List[ArticleWithSentiment]) -> SentimentScore:
    if not scored:
        return SentimentScore(positive=0.0, negative=0.0, neutral=1.0, score=0.0, label="neutral")

    n = len(scored)
    pos = sum(a.sentiment.positive for a in scored) / n
    neg = sum(a.sentiment.negative for a in scored) / n
    neu = sum(a.sentiment.neutral for a in scored) / n

    if pos >= neg and pos >= neu:
        label = "positive"
    elif neg >= pos and neg >= neu:
        label = "negative"
    else:
        label = "neutral"

    return SentimentScore(positive=pos, negative=neg, neutral=neu, score=pos - neg, label=label)
