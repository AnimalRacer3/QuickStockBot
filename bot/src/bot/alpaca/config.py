from __future__ import annotations

import os
from dataclasses import dataclass

_PAPER_BASE = "https://paper-api.alpaca.markets"
_LIVE_BASE = "https://api.alpaca.markets"
_DATA_BASE = "https://data.alpaca.markets"


@dataclass(frozen=True)
class AlpacaConfig:
    api_key: str
    secret_key: str
    base_url: str
    data_url: str = _DATA_BASE
    is_paper: bool = True

    @classmethod
    def from_env(cls) -> "AlpacaConfig":
        key = os.environ.get("ALPACA_API_KEY", "")
        secret = os.environ.get("ALPACA_API_SECRET", "")
        paper_raw = os.environ.get("PAPER_TRADING")

        if not key or not secret:
            raise EnvironmentError(
                "ALPACA_API_KEY and ALPACA_API_SECRET must both be set."
            )

        if paper_raw is None:
            raise EnvironmentError(
                "PAPER_TRADING must be explicitly set to 'true' or 'false'. "
                "Refusing to start without an explicit paper/live choice."
            )

        paper_raw_lower = paper_raw.strip().lower()
        if paper_raw_lower not in ("true", "false"):
            raise ValueError(
                f"PAPER_TRADING must be 'true' or 'false', got: {paper_raw!r}"
            )

        is_paper = paper_raw_lower == "true"

        if not is_paper:
            # Explicit second confirmation required to prevent accidental live trading.
            confirmed = os.environ.get("ALPACA_LIVE_CONFIRMED", "").strip().lower()
            if confirmed != "true":
                raise EnvironmentError(
                    "Live trading requires ALPACA_LIVE_CONFIRMED=true in addition to "
                    "PAPER_TRADING=false. Set both env vars to enable live trading."
                )

        return cls(
            api_key=key,
            secret_key=secret,
            base_url=_PAPER_BASE if is_paper else _LIVE_BASE,
            is_paper=is_paper,
        )
