"""Tests for AlpacaConfig — paper/live guard and env-var loading."""
from __future__ import annotations

import pytest

from bot.alpaca.config import AlpacaConfig


class TestPaperConfig:
    def test_loads_paper_config(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ALPACA_ENV", "paper")
        monkeypatch.setenv("ALPACA_PAPER_KEY", "pk-test")
        monkeypatch.setenv("ALPACA_PAPER_SECRET", "sk-test")

        cfg = AlpacaConfig.from_env()

        assert cfg.is_paper is True
        assert cfg.api_key == "pk-test"
        assert cfg.secret_key == "sk-test"
        assert "paper" in cfg.base_url

    def test_paper_is_default_when_env_not_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("ALPACA_ENV", raising=False)
        monkeypatch.setenv("ALPACA_PAPER_KEY", "pk-test")
        monkeypatch.setenv("ALPACA_PAPER_SECRET", "sk-test")

        cfg = AlpacaConfig.from_env()
        assert cfg.is_paper is True

    def test_paper_missing_key_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ALPACA_ENV", "paper")
        monkeypatch.delenv("ALPACA_PAPER_KEY", raising=False)
        monkeypatch.delenv("ALPACA_PAPER_SECRET", raising=False)

        with pytest.raises(EnvironmentError, match="ALPACA_PAPER_KEY"):
            AlpacaConfig.from_env()


class TestLiveGuard:
    def test_live_requires_live_keys(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ALPACA_ENV", "live")
        monkeypatch.delenv("ALPACA_LIVE_KEY", raising=False)
        monkeypatch.delenv("ALPACA_LIVE_SECRET", raising=False)

        with pytest.raises(EnvironmentError, match="ALPACA_LIVE_KEY"):
            AlpacaConfig.from_env()

    def test_live_missing_secret_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ALPACA_ENV", "live")
        monkeypatch.setenv("ALPACA_LIVE_KEY", "lk-test")
        monkeypatch.delenv("ALPACA_LIVE_SECRET", raising=False)

        with pytest.raises(EnvironmentError):
            AlpacaConfig.from_env()

    def test_live_config_uses_live_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ALPACA_ENV", "live")
        monkeypatch.setenv("ALPACA_LIVE_KEY", "lk-test")
        monkeypatch.setenv("ALPACA_LIVE_SECRET", "ls-test")

        cfg = AlpacaConfig.from_env()

        assert cfg.is_paper is False
        assert "paper" not in cfg.base_url
        assert cfg.api_key == "lk-test"

    def test_invalid_env_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ALPACA_ENV", "staging")

        with pytest.raises(ValueError, match="paper.*live"):
            AlpacaConfig.from_env()

    def test_paper_config_cannot_hit_live_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ALPACA_ENV", "paper")
        monkeypatch.setenv("ALPACA_PAPER_KEY", "pk-test")
        monkeypatch.setenv("ALPACA_PAPER_SECRET", "sk-test")

        cfg = AlpacaConfig.from_env()
        # Paper config must never point at the live broker URL
        assert "paper-api.alpaca.markets" in cfg.base_url
        assert "paper-api" in cfg.base_url
