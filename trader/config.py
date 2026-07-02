"""Load and validate config.yaml + .env.

Both files are read from the directory containing the running executable
(or the current working directory when run from source), never bundled
into the PyInstaller binary itself.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv


class ConfigError(Exception):
    """Raised for missing/invalid configuration or secrets."""


def app_dir() -> Path:
    """Directory containing the running exe, or the repo root when run from source."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class MACDConfig:
    fast: int = 12
    slow: int = 26
    signal: int = 9
    mode: str = "positive_or_rising"  # "positive_or_rising" | "positive_only"


@dataclass(frozen=True)
class PatternToggles:
    morning_star: bool = True
    three_white_soldiers: bool = True
    rising_three_methods: bool = True
    pullback: bool = True
    breakout_base: bool = True


@dataclass(frozen=True)
class AnthropicConfig:
    model: str = "claude-sonnet-4-6"
    max_tokens: int = 2000
    max_candidates: int = 15


@dataclass(frozen=True)
class Paths:
    base_dir: Path
    journal_dir: Path
    logs_dir: Path
    replay_dir: Path
    performance_db: Path
    runs_csv: Path
    reports_dir: Path

    def ensure(self) -> None:
        for d in (self.base_dir, self.journal_dir, self.logs_dir, self.replay_dir, self.reports_dir):
            d.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class Config:
    mode: str
    timezone: str
    daily_kill_switch_pct: float
    max_positions: int
    risk_per_trade_pct: float
    max_position_pct_bp: float
    daily_profit_giveback_pct: float
    no_trade_cutoff_hours: float
    stop_loss_pct: float
    take_profit_pct: float
    trail_off_trigger_pct: float
    trail_off_scale_out_pct: float
    force_close_offset_min: float
    watchlist_size: int
    price_min: float
    price_max: float
    min_rvol: float
    max_float_millions: float
    require_news_catalyst: bool
    overextension_pct: float
    z_hour_cutoff: float
    alpaca_data_feed: str
    macd: MACDConfig
    patterns: PatternToggles
    anthropic: AnthropicConfig
    paths: Paths

    @property
    def is_live(self) -> bool:
        return self.mode.upper() == "LIVE"


_REQUIRED_TOP_LEVEL = [
    "mode", "timezone", "daily_kill_switch_pct", "max_positions",
    "risk_per_trade_pct", "max_position_pct_bp", "daily_profit_giveback_pct",
    "no_trade_cutoff_hours", "stop_loss_pct", "take_profit_pct",
    "trail_off_trigger_pct", "trail_off_scale_out_pct", "force_close_offset_min",
    "watchlist_size", "price_min", "price_max", "min_rvol", "max_float_millions",
    "require_news_catalyst", "overextension_pct", "z_hour_cutoff",
]


def load_config(path: Path | None = None) -> Config:
    """Load config.yaml from the exe directory (or an explicit path).

    Relative `paths.*` entries are resolved against the directory containing
    *this* config.yaml, not the caller's own app_dir() -- so passing an
    explicit `path` (e.g. a trader.exe distribution's config.yaml from a
    dev-machine script) makes fixtures/journals/etc. land next to that config,
    matching exactly where trader.exe itself will look for them.
    """
    base = app_dir()
    cfg_path = path or (base / "config.yaml")
    if not cfg_path.exists():
        raise ConfigError(f"config.yaml not found at {cfg_path}")
    base = cfg_path.resolve().parent

    with open(cfg_path, "r", encoding="utf-8") as fh:
        raw: dict[str, Any] = yaml.safe_load(fh) or {}

    missing = [k for k in _REQUIRED_TOP_LEVEL if k not in raw]
    if missing:
        raise ConfigError(f"config.yaml missing required keys: {missing}")

    if raw["mode"].upper() not in ("DRY_RUN", "LIVE"):
        raise ConfigError(f"mode must be DRY_RUN or LIVE, got {raw['mode']!r}")

    macd_raw = raw.get("macd", {})
    macd = MACDConfig(
        fast=int(macd_raw.get("fast", 12)),
        slow=int(macd_raw.get("slow", 26)),
        signal=int(macd_raw.get("signal", 9)),
        mode=macd_raw.get("mode", "positive_or_rising"),
    )

    patterns_raw = raw.get("patterns", {})
    pattern_field_names = {f.name for f in fields(PatternToggles)}
    patterns = PatternToggles(**{k: v for k, v in patterns_raw.items() if k in pattern_field_names})

    anthropic_raw = raw.get("anthropic", {})
    anthropic_cfg = AnthropicConfig(
        model=anthropic_raw.get("model", "claude-sonnet-4-6"),
        max_tokens=int(anthropic_raw.get("max_tokens", 2000)),
        max_candidates=int(anthropic_raw.get("max_candidates", 15)),
    )

    paths_raw = raw.get("paths", {})

    def _p(key: str, default: str) -> Path:
        value = paths_raw.get(key, default)
        p = Path(value)
        return p if p.is_absolute() else (base / p)

    paths = Paths(
        base_dir=_p("base_dir", "./trading"),
        journal_dir=_p("journal_dir", "./trading/journal"),
        logs_dir=_p("logs_dir", "./trading/logs"),
        replay_dir=_p("replay_dir", "./trading/replay"),
        performance_db=_p("performance_db", "./trading/performance_db.json"),
        runs_csv=_p("runs_csv", "./trading/runs.csv"),
        reports_dir=_p("reports_dir", "./trading"),
    )

    return Config(
        mode=raw["mode"].upper(),
        timezone=raw["timezone"],
        daily_kill_switch_pct=float(raw["daily_kill_switch_pct"]),
        max_positions=int(raw["max_positions"]),
        risk_per_trade_pct=float(raw["risk_per_trade_pct"]),
        max_position_pct_bp=float(raw["max_position_pct_bp"]),
        daily_profit_giveback_pct=float(raw["daily_profit_giveback_pct"]),
        no_trade_cutoff_hours=float(raw["no_trade_cutoff_hours"]),
        stop_loss_pct=float(raw["stop_loss_pct"]),
        take_profit_pct=float(raw["take_profit_pct"]),
        trail_off_trigger_pct=float(raw["trail_off_trigger_pct"]),
        trail_off_scale_out_pct=float(raw["trail_off_scale_out_pct"]),
        force_close_offset_min=float(raw["force_close_offset_min"]),
        watchlist_size=int(raw["watchlist_size"]),
        price_min=float(raw["price_min"]),
        price_max=float(raw["price_max"]),
        min_rvol=float(raw["min_rvol"]),
        max_float_millions=float(raw["max_float_millions"]),
        require_news_catalyst=bool(raw["require_news_catalyst"]),
        overextension_pct=float(raw["overextension_pct"]),
        z_hour_cutoff=float(raw["z_hour_cutoff"]),
        alpaca_data_feed=str(raw.get("alpaca_data_feed", "iex")),
        macd=macd,
        patterns=patterns,
        anthropic=anthropic_cfg,
        paths=paths,
    )


@dataclass(frozen=True)
class Secrets:
    alpaca_key: str
    alpaca_secret: str
    anthropic_api_key: str


def load_secrets(env_path: Path | None = None) -> Secrets:
    """Load secrets from a .env file next to the exe (or an explicit path).

    Pass `env_path` alongside an explicit `load_config(path)` to read the
    same distribution directory's `.env` rather than the caller's own app_dir().
    """
    env_path = env_path or (app_dir() / ".env")
    if env_path.exists():
        load_dotenv(env_path, override=True)

    alpaca_key = os.environ.get("ALPACA_KEY", "")
    alpaca_secret = os.environ.get("ALPACA_SECRET", "")
    anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY", "")

    missing = [
        name for name, value in (
            ("ALPACA_KEY", alpaca_key),
            ("ALPACA_SECRET", alpaca_secret),
            ("ANTHROPIC_API_KEY", anthropic_api_key),
        )
        if not value
    ]
    if missing:
        raise ConfigError(
            f"Missing required secrets in .env ({env_path}): {', '.join(missing)}"
        )
    return Secrets(alpaca_key=alpaca_key, alpaca_secret=alpaca_secret, anthropic_api_key=anthropic_api_key)
