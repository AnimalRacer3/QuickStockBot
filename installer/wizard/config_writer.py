"""
Config writer for the QuickStockBot installer wizard.

Writes secrets to a mode-0600 .env file and non-secret settings to
config.json, then registers an OS-appropriate autostart entry.
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import stat
import subprocess
import uuid
from pathlib import Path
from typing import Any

_APP_NAME = "quickstockbot"
_TASK_NAME = "QuickStockBotService"
_LAUNCHD_LABEL = "com.quickstockbot.service"


# ── Config directory ──────────────────────────────────────────────────────────


def get_config_dir() -> Path:
    system = platform.system()
    if system == "Windows":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home())
        return Path(base) / "QuickStockBot"
    return Path.home() / f".{_APP_NAME}"


# ── Write config ──────────────────────────────────────────────────────────────


def write_config(settings: dict[str, Any]) -> tuple[Path, str]:
    """
    Write .env (secrets) and config.json (tunables) to the config directory.

    Returns ``(config_dir, bot_id)``.
    """
    config_dir = get_config_dir()
    config_dir.mkdir(parents=True, exist_ok=True)

    bot_id: str = settings.get("bot_id") or str(uuid.uuid4())

    _write_env(config_dir, bot_id, settings)
    _write_config_json(config_dir, settings)

    return config_dir, bot_id


def _write_env(config_dir: Path, bot_id: str, s: dict[str, Any]) -> None:
    env_path = config_dir / ".env"

    lines = [
        f"BOT_ID={bot_id}",
        f"RELAY_URL={s['relay_url']}",
        f"LICENSE_KEY={s['license_key']}",
        f"CONNECTION_PASSWORD={s['connection_password']}",
        "BROKER=alpaca",
        f"ALPACA_API_KEY={s['paper_api_key']}",
        f"ALPACA_API_SECRET={s['paper_api_secret']}",
        f"PAPER_TRADING={'true' if s.get('paper_trading', True) else 'false'}",
        f"LOG_LEVEL={s.get('log_level', 'info')}",
    ]

    for env_key, settings_key in [
        ("ALPACA_LIVE_API_KEY", "live_api_key"),
        ("ALPACA_LIVE_API_SECRET", "live_api_secret"),
        ("FINNHUB_API_KEY", "finnhub_api_key"),
        ("NEWSAPI_API_KEY", "newsapi_api_key"),
        ("BENZINGA_API_KEY", "benzinga_api_key"),
    ]:
        if s.get(settings_key):
            lines.append(f"{env_key}={s[settings_key]}")

    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Restrict to owner read/write on POSIX; Windows uses ACLs.
    if platform.system() != "Windows":
        env_path.chmod(stat.S_IRUSR | stat.S_IWUSR)


def _write_config_json(config_dir: Path, s: dict[str, Any]) -> None:
    config: dict[str, Any] = {
        "scanner": {
            "pre_open_lead_hours": float(s.get("pre_open_lead_hours", 1.0)),
            "scan_duration_hours": float(s.get("scan_duration_hours", 3.0)),
            "relative_volume_min": float(s.get("relative_volume_min", 2.0)),
            "gap_up_min_pct": float(s.get("gap_up_min_pct", 5.0)),
            "max_float_shares": int(s.get("max_float_shares", 20_000_000)),
            "include_unknown_float": bool(s.get("include_unknown_float", True)),
            "active_tickers_n": int(s.get("active_tickers_n", 3)),
        },
        "patterns": {
            "enabled_patterns": list(
                s.get(
                    "enabled_patterns",
                    [
                        "bullish_engulfing",
                        "hammer",
                        "morning_star",
                        "bullish_continuation",
                    ],
                )
            ),
            "pattern_candle_lookback": int(s.get("pattern_candle_lookback", 5)),
            "macd_fast": int(s.get("macd_fast", 12)),
            "macd_slow": int(s.get("macd_slow", 26)),
            "macd_signal": int(s.get("macd_signal", 9)),
            "macd_enforce_above_zero": bool(s.get("macd_enforce_above_zero", True)),
        },
        "risk": {
            "daily_max_loss_pct": float(s.get("daily_max_loss_pct", -2.0)),
            "daily_profit_target_pct": float(s.get("daily_profit_target_pct", 3.0)),
            "override_risk_per_trade": bool(s.get("override_risk_per_trade", False)),
            "risk_per_trade_pct": float(s.get("risk_per_trade_pct", 1.0)),
            "exit_mode": str(s.get("exit_mode", "dump")),
            "trail_off_trigger": str(s.get("trail_off_trigger", "per_candle")),
            "trail_off_fraction_per_candle": float(
                s.get("trail_off_fraction_per_candle", 0.25)
            ),
        },
    }
    (config_dir / "config.json").write_text(
        json.dumps(config, indent=2), encoding="utf-8"
    )


# ── Autostart ─────────────────────────────────────────────────────────────────


def setup_autostart(exe_path: str, config_dir: Path) -> None:
    system = platform.system()
    if system == "Windows":
        _autostart_windows(exe_path)
    elif system == "Linux":
        _autostart_linux(exe_path)
    elif system == "Darwin":
        _autostart_macos(exe_path)


def _autostart_windows(exe_path: str) -> None:
    subprocess.run(
        [
            "schtasks",
            "/create",
            "/tn",
            _TASK_NAME,
            "/tr",
            f'"{exe_path}" --service',
            "/sc",
            "ONLOGON",
            "/rl",
            "HIGHEST",
            "/f",
        ],
        check=True,
        capture_output=True,
    )


def _autostart_linux(exe_path: str) -> None:
    service_dir = Path.home() / ".config" / "systemd" / "user"
    service_dir.mkdir(parents=True, exist_ok=True)

    service_content = (
        "[Unit]\n"
        "Description=QuickStockBot Trading Engine\n"
        "After=network.target\n\n"
        "[Service]\n"
        "Type=simple\n"
        f"ExecStart={exe_path} --service\n"
        "Restart=on-failure\n"
        "RestartSec=10\n\n"
        "[Install]\n"
        "WantedBy=default.target\n"
    )
    (service_dir / "quickstockbot.service").write_text(service_content)

    subprocess.run(["systemctl", "--user", "enable", "quickstockbot"], check=True)
    subprocess.run(["systemctl", "--user", "start", "quickstockbot"], check=True)


def _autostart_macos(exe_path: str) -> None:
    plist_dir = Path.home() / "Library" / "LaunchAgents"
    plist_dir.mkdir(parents=True, exist_ok=True)

    plist_content = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"'
        ' "http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
        '<plist version="1.0">\n'
        "<dict>\n"
        "    <key>Label</key>\n"
        f"    <string>{_LAUNCHD_LABEL}</string>\n"
        "    <key>ProgramArguments</key>\n"
        "    <array>\n"
        f"        <string>{exe_path}</string>\n"
        "        <string>--service</string>\n"
        "    </array>\n"
        "    <key>RunAtLoad</key>\n"
        "    <true/>\n"
        "    <key>KeepAlive</key>\n"
        "    <true/>\n"
        "</dict>\n"
        "</plist>\n"
    )
    plist_path = plist_dir / f"{_LAUNCHD_LABEL}.plist"
    plist_path.write_text(plist_content)

    subprocess.run(["launchctl", "load", str(plist_path)], check=True)


# ── Uninstall ─────────────────────────────────────────────────────────────────


def uninstall(config_dir: Path | None = None) -> None:
    """Remove autostart entries and wipe the config directory."""
    if config_dir is None:
        config_dir = get_config_dir()

    system = platform.system()
    if system == "Windows":
        subprocess.run(
            ["schtasks", "/delete", "/tn", _TASK_NAME, "/f"],
            capture_output=True,
        )
    elif system == "Linux":
        subprocess.run(
            ["systemctl", "--user", "stop", "quickstockbot"],
            capture_output=True,
        )
        subprocess.run(
            ["systemctl", "--user", "disable", "quickstockbot"],
            capture_output=True,
        )
        service_path = (
            Path.home() / ".config" / "systemd" / "user" / "quickstockbot.service"
        )
        service_path.unlink(missing_ok=True)
    elif system == "Darwin":
        plist_path = (
            Path.home() / "Library" / "LaunchAgents" / f"{_LAUNCHD_LABEL}.plist"
        )
        subprocess.run(
            ["launchctl", "unload", str(plist_path)],
            capture_output=True,
        )
        plist_path.unlink(missing_ok=True)

    if config_dir.exists():
        shutil.rmtree(config_dir)
