"""Input validation for the QuickStockBot setup wizard."""

from __future__ import annotations

from typing import Any, Protocol

import httpx

_ALPACA_PAPER_BASE = "https://paper-api.alpaca.markets"
_ALPACA_LIVE_BASE = "https://api.alpaca.markets"


class _HttpClient(Protocol):
    def get(self, url: str, **kwargs: Any) -> Any: ...


def validate_relay_url(url: str) -> str | None:
    """Return an error string or None if valid."""
    if not url or not url.strip():
        return "Relay URL is required."
    if not (url.startswith("wss://") or url.startswith("ws://")):
        return "Relay URL must start with ws:// or wss://."
    return None


def validate_license_key(key: str) -> str | None:
    if not key or not key.strip():
        return "License key is required."
    return None


def validate_connection_password(password: str, confirm: str) -> str | None:
    if not password:
        return "Connection password is required."
    if len(password) < 8:
        return "Connection password must be at least 8 characters."
    if password != confirm:
        return "Passwords do not match."
    return None


def validate_alpaca_keys(
    api_key: str,
    api_secret: str,
    paper: bool = True,
    http_client: _HttpClient | None = None,
) -> tuple[bool, str]:
    """
    Test Alpaca credentials by calling GET /v2/account.
    Returns (success, message).
    """
    if not api_key or not api_secret:
        return False, "API key and secret are required."

    base = _ALPACA_PAPER_BASE if paper else _ALPACA_LIVE_BASE
    from typing import cast

    client: _HttpClient = (
        http_client
        if http_client is not None
        else cast(_HttpClient, httpx.Client(timeout=10.0))
    )
    try:
        resp = client.get(
            f"{base}/v2/account",
            headers={
                "APCA-API-KEY-ID": api_key,
                "APCA-API-SECRET-KEY": api_secret,
            },
        )
        if resp.status_code == 200:
            return True, "Connection successful."
        if resp.status_code == 403:
            return False, "Invalid API key or secret (HTTP 403)."
        return False, f"Alpaca returned HTTP {resp.status_code}."
    except Exception as exc:
        return False, f"Network error: {exc}"


def validate_scanner_settings(settings: dict[str, Any]) -> dict[str, str]:
    """Validate scanner fields. Returns {field: error} for any invalid value."""
    errors: dict[str, str] = {}

    _check_float(errors, settings, "pre_open_lead_hours", lo=0.0, hi=8.0)
    _check_float(errors, settings, "scan_duration_hours", lo=0.5, hi=24.0)
    _check_float(errors, settings, "relative_volume_min", lo=1.0)
    _check_float(errors, settings, "gap_up_min_pct", lo=0.0)
    _check_int(errors, settings, "max_float_shares", lo=100_000)
    _check_int(errors, settings, "active_tickers_n", lo=1, hi=50)

    return errors


def validate_risk_settings(settings: dict[str, Any]) -> dict[str, str]:
    """Validate risk/exit fields. Returns {field: error} for any invalid value."""
    errors: dict[str, str] = {}

    dml = settings.get("daily_max_loss_pct")
    if dml is not None:
        try:
            v = float(dml)
            if v >= 0:
                errors["daily_max_loss_pct"] = "Must be negative (e.g. -2.0)."
            elif v < -100:
                errors["daily_max_loss_pct"] = "Cannot exceed -100%."
        except (TypeError, ValueError):
            errors["daily_max_loss_pct"] = "Must be a number."

    _check_float(errors, settings, "daily_profit_target_pct", lo=0.01)

    override = settings.get("override_risk_per_trade", False)
    rpt = settings.get("risk_per_trade_pct")
    if override and rpt is not None:
        try:
            v = float(rpt)
            dml_val = abs(float(settings.get("daily_max_loss_pct") or -2.0))
            if v <= 0:
                errors["risk_per_trade_pct"] = "Must be positive."
            elif v >= dml_val:
                errors["risk_per_trade_pct"] = (
                    f"Must be less than |daily_max_loss_pct| ({dml_val:.1f}%)."
                )
        except (TypeError, ValueError):
            errors["risk_per_trade_pct"] = "Must be a number."

    exit_mode = settings.get("exit_mode")
    if exit_mode is not None and exit_mode not in ("dump", "trail_off"):
        errors["exit_mode"] = "Must be 'dump' or 'trail_off'."

    trail_trigger = settings.get("trail_off_trigger")
    if trail_trigger is not None and trail_trigger not in (
        "per_candle",
        "candle_pattern",
    ):
        errors["trail_off_trigger"] = "Must be 'per_candle' or 'candle_pattern'."

    tfpc = settings.get("trail_off_fraction_per_candle")
    if tfpc is not None:
        try:
            v = float(tfpc)
            if not (0 < v <= 1.0):
                errors["trail_off_fraction_per_candle"] = (
                    "Must be between 0 (exclusive) and 1.0."
                )
        except (TypeError, ValueError):
            errors["trail_off_fraction_per_candle"] = "Must be a number."

    return errors


# ── helpers ───────────────────────────────────────────────────────────────────


def _check_float(
    errors: dict[str, str],
    settings: dict[str, Any],
    key: str,
    lo: float | None = None,
    hi: float | None = None,
) -> None:
    val = settings.get(key)
    if val is None:
        return
    try:
        v = float(val)
    except (TypeError, ValueError):
        errors[key] = "Must be a number."
        return
    if lo is not None and v < lo:
        errors[key] = f"Must be ≥ {lo}."
    elif hi is not None and v > hi:
        errors[key] = f"Must be ≤ {hi}."


def _check_int(
    errors: dict[str, str],
    settings: dict[str, Any],
    key: str,
    lo: int | None = None,
    hi: int | None = None,
) -> None:
    val = settings.get(key)
    if val is None:
        return
    try:
        v = int(val)
    except (TypeError, ValueError):
        errors[key] = "Must be an integer."
        return
    if lo is not None and v < lo:
        errors[key] = f"Must be ≥ {lo}."
    elif hi is not None and v > hi:
        errors[key] = f"Must be ≤ {hi}."
