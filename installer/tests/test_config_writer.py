"""Unit tests for the wizard config writer."""

from __future__ import annotations

import json
import os
import platform
import stat
from pathlib import Path
from unittest.mock import patch

import pytest

from wizard.config_writer import uninstall, write_config

SAMPLE: dict = {
    "relay_url": "wss://relay.quickstockbot.com",
    "license_key": "LIC-TEST-1234",
    "connection_password": "super_secret_pw",
    "paper_api_key": "PKT_PAPER_KEY",
    "paper_api_secret": "PAPER_SECRET",
    "paper_trading": True,
    # scanner
    "pre_open_lead_hours": 1.5,
    "scan_duration_hours": 4.0,
    "relative_volume_min": 3.0,
    "gap_up_min_pct": 7.5,
    "max_float_shares": 15_000_000,
    "include_unknown_float": False,
    "active_tickers_n": 5,
    # patterns
    "enabled_patterns": ["bullish_engulfing", "hammer"],
    "pattern_candle_lookback": 7,
    "macd_fast": 12,
    "macd_slow": 26,
    "macd_signal": 9,
    "macd_enforce_above_zero": True,
    # risk
    "daily_max_loss_pct": -3.0,
    "daily_profit_target_pct": 5.0,
    "override_risk_per_trade": True,
    "risk_per_trade_pct": 1.5,
    "exit_mode": "trail_off",
    "trail_off_trigger": "per_candle",
    "trail_off_fraction_per_candle": 0.33,
}


def _write(tmp_path: Path, overrides: dict | None = None) -> tuple[Path, str]:
    settings = dict(SAMPLE)
    if overrides:
        settings.update(overrides)
    with patch("wizard.config_writer.get_config_dir", return_value=tmp_path):
        return write_config(settings)


# ── .env ─────────────────────────────────────────────────────────────────────


def test_env_file_created(tmp_path: Path) -> None:
    _write(tmp_path)
    assert (tmp_path / ".env").exists()


def test_env_contains_secrets(tmp_path: Path) -> None:
    _write(tmp_path)
    content = (tmp_path / ".env").read_text()
    assert "LIC-TEST-1234" in content
    assert "PAPER_SECRET" in content
    assert "super_secret_pw" in content
    assert "RELAY_URL=wss://relay.quickstockbot.com" in content


def test_env_omits_missing_optional_keys(tmp_path: Path) -> None:
    _write(tmp_path)
    content = (tmp_path / ".env").read_text()
    assert "FINNHUB_API_KEY" not in content
    assert "NEWSAPI_API_KEY" not in content
    assert "BENZINGA_API_KEY" not in content


def test_env_includes_optional_news_keys(tmp_path: Path) -> None:
    _write(tmp_path, {"finnhub_api_key": "FH_KEY", "newsapi_api_key": "NA_KEY"})
    content = (tmp_path / ".env").read_text()
    assert "FINNHUB_API_KEY=FH_KEY" in content
    assert "NEWSAPI_API_KEY=NA_KEY" in content


@pytest.mark.skipif(
    platform.system() == "Windows", reason="POSIX-only permission check"
)
def test_env_file_mode_0600(tmp_path: Path) -> None:
    _write(tmp_path)
    mode = stat.S_IMODE(os.stat(tmp_path / ".env").st_mode)
    assert mode == (stat.S_IRUSR | stat.S_IWUSR), f"Expected 0o600, got {oct(mode)}"


# ── config.json ───────────────────────────────────────────────────────────────


def test_config_json_created(tmp_path: Path) -> None:
    _write(tmp_path)
    assert (tmp_path / "config.json").exists()


def test_config_json_scanner_section(tmp_path: Path) -> None:
    _write(tmp_path)
    cfg = json.loads((tmp_path / "config.json").read_text())
    s = cfg["scanner"]
    assert s["pre_open_lead_hours"] == 1.5
    assert s["scan_duration_hours"] == 4.0
    assert s["relative_volume_min"] == 3.0
    assert s["gap_up_min_pct"] == 7.5
    assert s["max_float_shares"] == 15_000_000
    assert s["include_unknown_float"] is False
    assert s["active_tickers_n"] == 5


def test_config_json_patterns_section(tmp_path: Path) -> None:
    _write(tmp_path)
    cfg = json.loads((tmp_path / "config.json").read_text())
    p = cfg["patterns"]
    assert p["enabled_patterns"] == ["bullish_engulfing", "hammer"]
    assert p["pattern_candle_lookback"] == 7
    assert p["macd_enforce_above_zero"] is True


def test_config_json_risk_section(tmp_path: Path) -> None:
    _write(tmp_path)
    cfg = json.loads((tmp_path / "config.json").read_text())
    r = cfg["risk"]
    assert r["daily_max_loss_pct"] == -3.0
    assert r["daily_profit_target_pct"] == 5.0
    assert r["override_risk_per_trade"] is True
    assert r["risk_per_trade_pct"] == pytest.approx(1.5)
    assert r["exit_mode"] == "trail_off"
    assert r["trail_off_fraction_per_candle"] == pytest.approx(0.33)


# ── bot_id ────────────────────────────────────────────────────────────────────


def test_bot_id_auto_generated(tmp_path: Path) -> None:
    import re

    _, bot_id = _write(tmp_path)
    assert re.fullmatch(r"[0-9a-f-]{36}", bot_id)


def test_bot_id_preserved_when_provided(tmp_path: Path) -> None:
    fixed = "aaaabbbb-cccc-dddd-eeee-ffffaaaabbbb"
    _, bot_id = _write(tmp_path, {"bot_id": fixed})
    assert bot_id == fixed


def test_bot_id_written_to_env(tmp_path: Path) -> None:
    _, bot_id = _write(tmp_path)
    content = (tmp_path / ".env").read_text()
    assert f"BOT_ID={bot_id}" in content


# ── uninstall ─────────────────────────────────────────────────────────────────


def test_uninstall_removes_config_dir(tmp_path: Path) -> None:
    (tmp_path / "data.txt").write_text("hello")
    with (
        patch("subprocess.run"),
        patch("wizard.config_writer.platform.system", return_value="Linux"),
    ):
        uninstall(tmp_path)
    assert not tmp_path.exists()


def test_uninstall_tolerates_missing_dir(tmp_path: Path) -> None:
    missing = tmp_path / "nonexistent"
    with (
        patch("subprocess.run"),
        patch("wizard.config_writer.platform.system", return_value="Linux"),
    ):
        uninstall(missing)  # should not raise
