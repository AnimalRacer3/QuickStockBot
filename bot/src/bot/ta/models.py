from __future__ import annotations

from pydantic import BaseModel, Field


class MacdState(BaseModel):
    value: float
    slope: float
    hist: float
    favorability: float = Field(ge=-1.0, le=1.0)
    eligible: bool


class PatternMatch(BaseModel):
    matched: bool
    tag: str
    strength: float = Field(ge=0.0, le=1.0)


class TickerTA(BaseModel):
    symbol: str
    macd_state: MacdState
    pattern_tags: list[str]
    score: float = Field(ge=0.0, le=100.0)
