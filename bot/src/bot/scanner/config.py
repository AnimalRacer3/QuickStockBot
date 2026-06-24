from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class ScannerConfig:
    # Window
    pre_open_lead_hours: float = 1.0
    scan_duration_hours: float = 3.0
    scanner_refresh_seconds: int = 60

    # Price filter
    min_price: float = 1.0
    max_price: float = 20.0

    # Momentum filters
    gap_up_min_pct: float = 5.0
    relative_volume_min: float = 2.0
    max_float_shares: int = 20_000_000

    # News
    require_news: bool = True

    # Unknown-float handling
    include_unknown_float: bool = True

    # Active set
    active_tickers_n: int = 3
    whitelist_symbols: list[str] = field(default_factory=list)

    # Prior-profit bias
    prior_profit_bias_weight: float = 0.5

    # Leader/laggard
    leader_similarity_threshold: float = 0.7

    @classmethod
    def from_env(cls) -> ScannerConfig:
        def _float(key: str, default: float) -> float:
            return float(os.environ.get(key, default))

        def _int(key: str, default: int) -> int:
            return int(os.environ.get(key, default))

        def _bool(key: str, default: bool) -> bool:
            v = os.environ.get(key)
            if v is None:
                return default
            return v.lower() in {"1", "true", "yes"}

        return cls(
            pre_open_lead_hours=_float("PRE_OPEN_LEAD_HOURS", 1.0),
            scan_duration_hours=_float("SCAN_DURATION_HOURS", 3.0),
            scanner_refresh_seconds=_int("SCANNER_REFRESH_SECONDS", 60),
            min_price=_float("MIN_PRICE", 1.0),
            max_price=_float("MAX_PRICE", 20.0),
            gap_up_min_pct=_float("GAP_UP_MIN_PCT", 5.0),
            relative_volume_min=_float("RELATIVE_VOLUME_MIN", 2.0),
            max_float_shares=_int("MAX_FLOAT_SHARES", 20_000_000),
            require_news=_bool("REQUIRE_NEWS", True),
            include_unknown_float=_bool("INCLUDE_UNKNOWN_FLOAT", True),
            active_tickers_n=_int("ACTIVE_TICKERS_N", 3),
            whitelist_symbols=[
                s.strip()
                for s in os.environ.get("WHITELIST_SYMBOLS", "").split(",")
                if s.strip()
            ],
            prior_profit_bias_weight=_float("PRIOR_PROFIT_BIAS_WEIGHT", 0.5),
            leader_similarity_threshold=_float("LEADER_SIMILARITY_THRESHOLD", 0.7),
        )
