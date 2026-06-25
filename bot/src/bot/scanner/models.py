from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from bot.ta.models import MacdState


class ScanWindow(BaseModel):
    window_start: datetime
    window_end: datetime
    session_open: datetime


class ScanRole(str):
    LEADER = "leader"
    LAGGARD = "laggard"
    STANDALONE = "standalone"


class TickerState(BaseModel):
    symbol: str
    price: float
    prev_close: float
    gap_pct: float
    pct_change: float
    rvol: float
    float_shares: Optional[int]
    unknown_float: bool
    # tradable=False when unknown_float and include_unknown_float=False
    tradable: bool
    has_news: bool
    macd_state: MacdState
    pattern_tags: list[str]
    pattern_signature: list[float]
    role: str  # "leader" | "laggard" | "standalone"
    score: float


class ScanResult(BaseModel):
    window: ScanWindow
    candidates: list[TickerState]
    active_set: list[str]
    scanned_at: datetime
