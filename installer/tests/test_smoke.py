"""
Packaging smoke tests.

Verify that the installer package is importable, the Flask app starts and
serves the wizard HTML, and all API endpoints respond correctly.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from wizard.server import create_app


@pytest.fixture()
def client():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_status_endpoint(client) -> None:
    resp = client.get("/api/status")
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data["ok"] is True


def test_wizard_html_served(client) -> None:
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"QuickStockBot" in resp.data
    assert b"<form" not in resp.data or b"step" in resp.data  # has wizard UI


def test_wizard_html_is_valid_html(client) -> None:
    resp = client.get("/")
    text = resp.data.decode()
    assert "<!DOCTYPE html>" in text
    assert "</html>" in text


def test_validate_credentials_missing_relay(client) -> None:
    resp = client.post(
        "/api/validate/inputs",
        data=json.dumps(
            {
                "step": "credentials",
                "relay_url": "",
                "license_key": "KEY",
                "connection_password": "goodpass1",
                "connection_password_confirm": "goodpass1",
            }
        ),
        content_type="application/json",
    )
    data = json.loads(resp.data)
    assert data["valid"] is False
    assert "relay_url" in data["errors"]


def test_validate_credentials_bad_scheme(client) -> None:
    resp = client.post(
        "/api/validate/inputs",
        data=json.dumps(
            {
                "step": "credentials",
                "relay_url": "http://relay.example.com",
                "license_key": "KEY",
                "connection_password": "goodpass1",
                "connection_password_confirm": "goodpass1",
            }
        ),
        content_type="application/json",
    )
    data = json.loads(resp.data)
    assert data["valid"] is False
    assert "relay_url" in data["errors"]


def test_validate_scanner_valid(client) -> None:
    resp = client.post(
        "/api/validate/inputs",
        data=json.dumps(
            {
                "step": "scanner",
                "pre_open_lead_hours": 1.0,
                "scan_duration_hours": 3.0,
                "relative_volume_min": 2.0,
                "gap_up_min_pct": 5.0,
                "max_float_shares": 20_000_000,
                "active_tickers_n": 3,
            }
        ),
        content_type="application/json",
    )
    data = json.loads(resp.data)
    assert data["valid"] is True


def test_validate_scanner_invalid_rvol(client) -> None:
    resp = client.post(
        "/api/validate/inputs",
        data=json.dumps({"step": "scanner", "relative_volume_min": 0.0}),
        content_type="application/json",
    )
    data = json.loads(resp.data)
    assert data["valid"] is False


def test_validate_risk_valid(client) -> None:
    resp = client.post(
        "/api/validate/inputs",
        data=json.dumps(
            {
                "step": "risk",
                "daily_max_loss_pct": -2.0,
                "daily_profit_target_pct": 3.0,
                "exit_mode": "dump",
            }
        ),
        content_type="application/json",
    )
    data = json.loads(resp.data)
    assert data["valid"] is True


def test_validate_alpaca_mocked(client) -> None:
    from unittest.mock import MagicMock

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_client = MagicMock()
    mock_client.get.return_value = mock_resp

    with patch("wizard.validator.httpx.Client", return_value=mock_client):
        resp = client.post(
            "/api/validate/alpaca",
            data=json.dumps({"api_key": "KEY", "api_secret": "SECRET", "paper": True}),
            content_type="application/json",
        )
    data = json.loads(resp.data)
    assert data["success"] is True


def test_install_writes_config(client, tmp_path: Path) -> None:
    settings = {
        "relay_url": "wss://relay.quickstockbot.com",
        "license_key": "LIC-TEST",
        "connection_password": "strongpass1",
        "paper_api_key": "PKEY",
        "paper_api_secret": "PSECRET",
    }
    with (
        patch("wizard.config_writer.get_config_dir", return_value=tmp_path),
        patch("wizard.config_writer.setup_autostart"),
    ):
        resp = client.post(
            "/api/install",
            data=json.dumps(settings),
            content_type="application/json",
        )
    data = json.loads(resp.data)
    assert data["success"] is True
    assert (tmp_path / ".env").exists()
    assert (tmp_path / "config.json").exists()


def test_wizard_html_contains_all_sections(client) -> None:
    text = client.get("/").data.decode()
    # Verify all major setting categories are present in the wizard
    for keyword in [
        "pre_open_lead_hours",
        "relative_volume_min",
        "gap_up_min_pct",
        "active_tickers_n",
        "macd_enforce_above_zero",
        "daily_max_loss_pct",
        "exit_mode",
        "trail_off",
    ]:
        assert keyword in text, f"Missing field reference in wizard HTML: {keyword}"
