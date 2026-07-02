"""record_bars.py must merge/append into <date>-watchlist.json across runs
(deduped by ticker) instead of overwriting it, and record an RVOL baseline
per ticker."""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

from scripts import record_bars
from trader.config import AnthropicConfig, Config, MACDConfig, Paths, PatternToggles, Secrets
from trader.models import Candle

RECORD_DATE = date(2024, 6, 14)  # a fully historical past day -- never "today"


def _config(tmp_path: Path) -> Config:
    return Config(
        mode="DRY_RUN", timezone="America/New_York",
        daily_kill_switch_pct=-10, max_positions=5, risk_per_trade_pct=2,
        max_position_pct_bp=25, daily_profit_giveback_pct=25, no_trade_cutoff_hours=2,
        stop_loss_pct=1, take_profit_pct=3, trail_off_trigger_pct=1.5, trail_off_scale_out_pct=25,
        force_close_offset_min=5, watchlist_size=5, price_min=2, price_max=20, min_rvol=5,
        max_float_millions=20, require_news_catalyst=True, overextension_pct=3, z_hour_cutoff=1.0,
        alpaca_data_feed="iex",
        macd=MACDConfig(), patterns=PatternToggles(), anthropic=AnthropicConfig(),
        paths=Paths(
            base_dir=tmp_path, journal_dir=tmp_path / "journal", logs_dir=tmp_path / "logs",
            replay_dir=tmp_path / "replay", performance_db=tmp_path / "performance_db.json",
            runs_csv=tmp_path / "runs.csv", reports_dir=tmp_path,
        ),
    )


class _FakeAlpacaData:
    def __init__(self, api_key, api_secret, paper=True, feed="iex"):
        pass

    def get_minute_bars_for_day(self, ticker: str, record_date) -> list[Candle]:
        return [
            Candle(
                timestamp=datetime(record_date.year, record_date.month, record_date.day, 9, 30),
                open=10.0, high=10.1, low=9.9, close=10.0, volume=500,
            )
        ]

    def get_avg_daily_volume(self, ticker: str) -> float:
        return 2500.0


def _patch(monkeypatch, tmp_path):
    config = _config(tmp_path)
    monkeypatch.setattr(record_bars, "load_config", lambda path=None: config)
    monkeypatch.setattr(
        record_bars, "load_secrets",
        lambda env_path=None: Secrets(alpaca_key="k", alpaca_secret="s", anthropic_api_key="a"),
    )
    monkeypatch.setattr(record_bars, "AlpacaData", _FakeAlpacaData)
    return config


def _run(monkeypatch, tickers: str) -> int:
    monkeypatch.setattr(
        "sys.argv", ["record_bars.py", "--date", RECORD_DATE.isoformat(), "--tickers", tickers],
    )
    return record_bars.main()


def test_second_recording_appends_new_ticker_without_dropping_first(tmp_path, monkeypatch):
    config = _patch(monkeypatch, tmp_path)

    assert _run(monkeypatch, "AAPL") == 0
    assert _run(monkeypatch, "TSLA") == 0

    watchlist_path = config.paths.replay_dir / f"{RECORD_DATE.isoformat()}-watchlist.json"
    watchlist = json.loads(watchlist_path.read_text(encoding="utf-8"))
    tickers = {row["ticker"] for row in watchlist}
    assert tickers == {"AAPL", "TSLA"}
    assert len(watchlist) == 2  # not duplicated, not overwritten


def test_recording_same_ticker_again_updates_in_place_not_duplicated(tmp_path, monkeypatch):
    config = _patch(monkeypatch, tmp_path)

    assert _run(monkeypatch, "AAPL,TSLA") == 0
    assert _run(monkeypatch, "AAPL") == 0  # re-record just AAPL

    watchlist_path = config.paths.replay_dir / f"{RECORD_DATE.isoformat()}-watchlist.json"
    watchlist = json.loads(watchlist_path.read_text(encoding="utf-8"))
    assert len(watchlist) == 2
    tickers = [row["ticker"] for row in watchlist]
    assert tickers.count("AAPL") == 1
    assert tickers.count("TSLA") == 1


def test_watchlist_records_rvol_baseline(tmp_path, monkeypatch):
    config = _patch(monkeypatch, tmp_path)

    assert _run(monkeypatch, "AAPL") == 0

    watchlist_path = config.paths.replay_dir / f"{RECORD_DATE.isoformat()}-watchlist.json"
    watchlist = json.loads(watchlist_path.read_text(encoding="utf-8"))
    assert watchlist[0]["avg_volume_baseline"] == 2500.0
