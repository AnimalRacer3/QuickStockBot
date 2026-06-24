from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class Article(BaseModel):
    symbol: str
    headline: str
    summary: str
    source: str
    url: str
    published_at: datetime


class SentimentScore(BaseModel):
    positive: float
    negative: float
    neutral: float
    score: float   # positive - negative
    label: str     # "positive" | "negative" | "neutral"


class ArticleWithSentiment(BaseModel):
    article: Article
    sentiment: SentimentScore


class TickerSentiment(BaseModel):
    symbol: str
    articles: list[ArticleWithSentiment]
    aggregate: SentimentScore
