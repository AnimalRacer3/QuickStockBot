from __future__ import annotations

import os
from dataclasses import dataclass, field


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
        env = os.environ.get("ALPACA_ENV", "paper").lower()

        if env == "live":
            key = os.environ.get("ALPACA_LIVE_KEY", "")
            secret = os.environ.get("ALPACA_LIVE_SECRET", "")
            if not key or not secret:
                raise EnvironmentError(
                    "ALPACA_ENV=live requires ALPACA_LIVE_KEY and ALPACA_LIVE_SECRET to be set."
                )
            return cls(
                api_key=key,
                secret_key=secret,
                base_url=_LIVE_BASE,
                is_paper=False,
            )

        if env == "paper":
            key = os.environ.get("ALPACA_PAPER_KEY", "")
            secret = os.environ.get("ALPACA_PAPER_SECRET", "")
            if not key or not secret:
                raise EnvironmentError(
                    "ALPACA_ENV=paper requires ALPACA_PAPER_KEY and ALPACA_PAPER_SECRET to be set."
                )
            return cls(
                api_key=key,
                secret_key=secret,
                base_url=_PAPER_BASE,
                is_paper=True,
            )

        raise ValueError(f"ALPACA_ENV must be 'paper' or 'live', got: {env!r}")
