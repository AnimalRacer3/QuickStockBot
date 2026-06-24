"""Placeholder test — verifies the test harness is wired up correctly."""

from bot import __version__


def test_version() -> None:
    assert __version__ == "0.1.0"


def test_placeholder() -> None:
    assert 1 + 1 == 2
