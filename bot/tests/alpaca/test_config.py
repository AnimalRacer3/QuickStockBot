"""Tests for AlpacaConfig — paper/live guard and env-var loading."""

from __future__ import annotations

import pytest

from bot.alpaca.config import AlpacaConfig


def _base_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set minimal valid paper-mode env vars."""
    monkeypatch.setenv("ALPACA_API_KEY", "test-key")
    monkeypatch.setenv("ALPACA_API_SECRET", "test-secret")
    monkeypatch.setenv("PAPER_TRADING", "true")
    monkeypatch.delenv("ALPACA_LIVE_CONFIRMED", raising=False)


class TestPaperConfig:
    def test_loads_paper_config(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _base_env(monkeypatch)
        cfg = AlpacaConfig.from_env()
        assert cfg.is_paper is True
        assert cfg.api_key == "test-key"
        assert "paper" in cfg.base_url

    def test_paper_url_never_points_to_live(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _base_env(monkeypatch)
        cfg = AlpacaConfig.from_env()
        assert "paper-api.alpaca.markets" in cfg.base_url

    def test_missing_key_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _base_env(monkeypatch)
        monkeypatch.delenv("ALPACA_API_KEY")
        with pytest.raises(EnvironmentError, match="ALPACA_API_KEY"):
            AlpacaConfig.from_env()

    def test_missing_secret_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _base_env(monkeypatch)
        monkeypatch.delenv("ALPACA_API_SECRET")
        with pytest.raises(EnvironmentError, match="ALPACA_API_SECRET"):
            AlpacaConfig.from_env()

    def test_missing_paper_trading_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ALPACA_API_KEY", "k")
        monkeypatch.setenv("ALPACA_API_SECRET", "s")
        monkeypatch.delenv("PAPER_TRADING", raising=False)
        with pytest.raises(EnvironmentError, match="PAPER_TRADING"):
            AlpacaConfig.from_env()

    def test_invalid_paper_trading_value_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _base_env(monkeypatch)
        monkeypatch.setenv("PAPER_TRADING", "yes")
        with pytest.raises(ValueError, match="true.*false"):
            AlpacaConfig.from_env()


class TestLiveGuard:
    def test_live_without_confirmed_flag_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ALPACA_API_KEY", "k")
        monkeypatch.setenv("ALPACA_API_SECRET", "s")
        monkeypatch.setenv("PAPER_TRADING", "false")
        monkeypatch.delenv("ALPACA_LIVE_CONFIRMED", raising=False)
        with pytest.raises(EnvironmentError, match="ALPACA_LIVE_CONFIRMED"):
            AlpacaConfig.from_env()

    def test_live_with_confirmed_flag_succeeds(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ALPACA_API_KEY", "lk")
        monkeypatch.setenv("ALPACA_API_SECRET", "ls")
        monkeypatch.setenv("PAPER_TRADING", "false")
        monkeypatch.setenv("ALPACA_LIVE_CONFIRMED", "true")
        cfg = AlpacaConfig.from_env()
        assert cfg.is_paper is False
        assert "paper" not in cfg.base_url

    def test_live_url_is_non_paper(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ALPACA_API_KEY", "lk")
        monkeypatch.setenv("ALPACA_API_SECRET", "ls")
        monkeypatch.setenv("PAPER_TRADING", "false")
        monkeypatch.setenv("ALPACA_LIVE_CONFIRMED", "true")
        cfg = AlpacaConfig.from_env()
        assert cfg.base_url == "https://api.alpaca.markets"

    def test_paper_trading_env_not_set_is_the_live_guard(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Prove the guard: without PAPER_TRADING the bot refuses to start."""
        monkeypatch.setenv("ALPACA_API_KEY", "k")
        monkeypatch.setenv("ALPACA_API_SECRET", "s")
        monkeypatch.delenv("PAPER_TRADING", raising=False)
        with pytest.raises(EnvironmentError):
            AlpacaConfig.from_env()
