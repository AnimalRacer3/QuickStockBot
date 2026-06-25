"""Unit tests for wizard input validation."""

from __future__ import annotations

from unittest.mock import MagicMock

from wizard.validator import (
    validate_alpaca_keys,
    validate_connection_password,
    validate_license_key,
    validate_relay_url,
    validate_risk_settings,
    validate_scanner_settings,
)

# ── relay URL ─────────────────────────────────────────────────────────────────


def test_relay_url_wss_valid() -> None:
    assert validate_relay_url("wss://relay.example.com") is None


def test_relay_url_ws_valid() -> None:
    assert validate_relay_url("ws://localhost:8080/ws") is None


def test_relay_url_empty() -> None:
    assert validate_relay_url("") is not None


def test_relay_url_whitespace_only() -> None:
    assert validate_relay_url("   ") is not None


def test_relay_url_http_rejected() -> None:
    err = validate_relay_url("http://relay.example.com")
    assert err is not None
    assert "ws" in err.lower()


# ── license key ───────────────────────────────────────────────────────────────


def test_license_key_valid() -> None:
    assert validate_license_key("QSB-ABCD-1234-WXYZ") is None


def test_license_key_empty() -> None:
    assert validate_license_key("") is not None


def test_license_key_whitespace() -> None:
    assert validate_license_key("   ") is not None


# ── connection password ───────────────────────────────────────────────────────


def test_password_valid() -> None:
    assert validate_connection_password("str0ngPass", "str0ngPass") is None


def test_password_too_short() -> None:
    err = validate_connection_password("abc", "abc")
    assert err is not None
    assert "8" in err


def test_password_mismatch() -> None:
    err = validate_connection_password("password1", "password2")
    assert err is not None
    assert "match" in err.lower()


def test_password_empty() -> None:
    assert validate_connection_password("", "") is not None


# ── Alpaca keys ───────────────────────────────────────────────────────────────


def _mock_http(status_code: int) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    client = MagicMock()
    client.get.return_value = resp
    return client


def test_alpaca_paper_200_ok() -> None:
    ok, msg = validate_alpaca_keys(
        "KEY", "SECRET", paper=True, http_client=_mock_http(200)
    )
    assert ok is True
    assert "success" in msg.lower()


def test_alpaca_paper_403_rejected() -> None:
    ok, msg = validate_alpaca_keys(
        "BAD", "BAD", paper=True, http_client=_mock_http(403)
    )
    assert ok is False
    assert "403" in msg or "Invalid" in msg


def test_alpaca_unexpected_500() -> None:
    ok, msg = validate_alpaca_keys("K", "S", paper=True, http_client=_mock_http(500))
    assert ok is False
    assert "500" in msg


def test_alpaca_empty_keys_rejected() -> None:
    ok, _ = validate_alpaca_keys("", "", paper=True)
    assert ok is False


def test_alpaca_network_error() -> None:
    client = MagicMock()
    client.get.side_effect = ConnectionError("host unreachable")
    ok, msg = validate_alpaca_keys("K", "S", paper=True, http_client=client)
    assert ok is False
    assert "error" in msg.lower() or "Network" in msg


def test_alpaca_live_endpoint_differs_from_paper() -> None:
    client = _mock_http(200)
    validate_alpaca_keys("K", "S", paper=False, http_client=client)
    call_url: str = client.get.call_args[0][0]
    assert "paper-api" not in call_url
    assert "api.alpaca.markets" in call_url


# ── scanner settings ──────────────────────────────────────────────────────────

VALID_SCANNER = {
    "pre_open_lead_hours": 1.0,
    "scan_duration_hours": 3.0,
    "relative_volume_min": 2.0,
    "gap_up_min_pct": 5.0,
    "max_float_shares": 20_000_000,
    "include_unknown_float": True,
    "active_tickers_n": 3,
}


def test_scanner_valid() -> None:
    assert validate_scanner_settings(VALID_SCANNER) == {}


def test_scanner_rvol_too_low() -> None:
    assert "relative_volume_min" in validate_scanner_settings(
        {"relative_volume_min": 0.5}
    )


def test_scanner_active_tickers_zero() -> None:
    assert "active_tickers_n" in validate_scanner_settings({"active_tickers_n": 0})


def test_scanner_active_tickers_too_high() -> None:
    assert "active_tickers_n" in validate_scanner_settings({"active_tickers_n": 51})


def test_scanner_lead_hours_too_high() -> None:
    assert "pre_open_lead_hours" in validate_scanner_settings(
        {"pre_open_lead_hours": 9.0}
    )


def test_scanner_float_too_small() -> None:
    assert "max_float_shares" in validate_scanner_settings({"max_float_shares": 999})


def test_scanner_non_numeric() -> None:
    assert "relative_volume_min" in validate_scanner_settings(
        {"relative_volume_min": "bad"}
    )


# ── risk settings ─────────────────────────────────────────────────────────────

VALID_RISK = {
    "daily_max_loss_pct": -2.0,
    "daily_profit_target_pct": 3.0,
    "override_risk_per_trade": True,
    "risk_per_trade_pct": 1.0,
    "exit_mode": "dump",
    "trail_off_trigger": "per_candle",
    "trail_off_fraction_per_candle": 0.25,
}


def test_risk_valid() -> None:
    assert validate_risk_settings(VALID_RISK) == {}


def test_risk_max_loss_positive_rejected() -> None:
    assert "daily_max_loss_pct" in validate_risk_settings({"daily_max_loss_pct": 2.0})


def test_risk_max_loss_zero_rejected() -> None:
    assert "daily_max_loss_pct" in validate_risk_settings({"daily_max_loss_pct": 0.0})


def test_risk_profit_target_negative_rejected() -> None:
    assert "daily_profit_target_pct" in validate_risk_settings(
        {"daily_profit_target_pct": -1.0}
    )


def test_risk_override_per_trade_exceeds_daily() -> None:
    errors = validate_risk_settings(
        {
            "daily_max_loss_pct": -2.0,
            "override_risk_per_trade": True,
            "risk_per_trade_pct": 3.0,
        }
    )
    assert "risk_per_trade_pct" in errors


def test_risk_override_per_trade_equal_daily_rejected() -> None:
    errors = validate_risk_settings(
        {
            "daily_max_loss_pct": -2.0,
            "override_risk_per_trade": True,
            "risk_per_trade_pct": 2.0,
        }
    )
    assert "risk_per_trade_pct" in errors


def test_risk_invalid_exit_mode() -> None:
    assert "exit_mode" in validate_risk_settings({"exit_mode": "unknown"})


def test_risk_trail_fraction_above_one() -> None:
    assert "trail_off_fraction_per_candle" in validate_risk_settings(
        {"trail_off_fraction_per_candle": 1.1}
    )


def test_risk_trail_fraction_zero_rejected() -> None:
    assert "trail_off_fraction_per_candle" in validate_risk_settings(
        {"trail_off_fraction_per_candle": 0.0}
    )


def test_risk_trail_fraction_one_valid() -> None:
    assert "trail_off_fraction_per_candle" not in validate_risk_settings(
        {"trail_off_fraction_per_candle": 1.0}
    )


def test_risk_invalid_trail_trigger() -> None:
    assert "trail_off_trigger" in validate_risk_settings({"trail_off_trigger": "bad"})
