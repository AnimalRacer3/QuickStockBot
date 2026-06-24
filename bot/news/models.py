from dataclasses import dataclass
from datetime import datetime


@dataclass
class Article:
    symbol: str
    headline: str
    summary: str
    source: str
    url: str
    published_at: datetime


@dataclass
class SentimentScore:
    positive: float
    negative: float
    neutral: float
    score: float   # composite: positive - negative
    label: str     # "positive" | "negative" | "neutral"


@dataclass
class ArticleWithSentiment:
    article: Article
    sentiment: SentimentScore


@dataclass
class TickerSentiment:
    symbol: str
    articles: list[ArticleWithSentiment]
    aggregate: SentimentScore
