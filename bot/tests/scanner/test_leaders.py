"""Tests for leader / laggard detection."""

from __future__ import annotations

from bot.scanner.leaders import assign_roles
from bot.scanner.models import TickerState
from bot.ta.models import MacdState

_MACD = MacdState(value=0.1, slope=0.01, hist=0.05, favorability=0.5, eligible=True)
_MACD_NEG = MacdState(value=-0.1, slope=-0.01, hist=-0.05, favorability=-0.5, eligible=False)


def _state(
    symbol: str,
    pct_change: float = 10.0,
    has_news: bool = True,
    sig: list[float] | None = None,
    macd: MacdState | None = None,
) -> TickerState:
    return TickerState(
        symbol=symbol,
        price=5.0,
        prev_close=4.5,
        gap_pct=pct_change,
        pct_change=pct_change,
        rvol=3.0,
        float_shares=10_000_000,
        unknown_float=False,
        tradable=True,
        has_news=has_news,
        macd_state=macd or _MACD,
        pattern_tags=[],
        pattern_signature=sig or [1.0, 0.5, 0.2, 0.1, 1.0],
        role="standalone",
        score=70.0,
    )


class TestAssignRoles:
    def test_singleton_is_standalone(self) -> None:
        states = [_state("SOLO")]
        result = assign_roles(states, similarity_threshold=0.7)
        assert result[0].role == "standalone"

    def test_similar_pair_leader_laggard(self) -> None:
        """Two symbols with identical signatures form a group; higher gainer = leader."""
        sig = [1.0, 0.5, 0.2, 0.1, 1.0]
        states = [
            _state("A", pct_change=20.0, sig=sig),
            _state("B", pct_change=10.0, sig=sig, has_news=True),
        ]
        result = assign_roles(states, similarity_threshold=0.7)
        by_sym = {s.symbol: s for s in result}
        assert by_sym["A"].role == "leader"
        assert by_sym["B"].role == "laggard"

    def test_laggard_without_news_is_standalone(self) -> None:
        sig = [1.0, 0.5, 0.2, 0.1, 1.0]
        states = [
            _state("A", pct_change=20.0, sig=sig),
            _state("B", pct_change=10.0, sig=sig, has_news=False),
        ]
        result = assign_roles(states, similarity_threshold=0.7)
        by_sym = {s.symbol: s for s in result}
        assert by_sym["A"].role == "leader"
        assert by_sym["B"].role == "standalone"

    def test_dissimilar_symbols_both_standalone(self) -> None:
        states = [
            _state("A", sig=[1.0, 0.0, 0.0, 0.0, 0.0]),
            _state("B", sig=[0.0, 0.0, 0.0, 0.0, 1.0]),
        ]
        result = assign_roles(states, similarity_threshold=0.7)
        assert all(s.role == "standalone" for s in result)

    def test_empty_list(self) -> None:
        assert assign_roles([], 0.7) == []

    def test_macd_favorability_breaks_pct_tie(self) -> None:
        """When pct_change is equal, higher MACD favorability elects the leader."""
        sig = [1.0, 0.5, 0.2, 0.1, 1.0]
        states = [
            _state("A", pct_change=10.0, sig=sig, macd=MacdState(value=0.5, slope=0.1, hist=0.1, favorability=0.9, eligible=True)),
            _state("B", pct_change=10.0, sig=sig, macd=MacdState(value=0.1, slope=0.0, hist=0.0, favorability=0.1, eligible=True)),
        ]
        result = assign_roles(states, similarity_threshold=0.7)
        by_sym = {s.symbol: s for s in result}
        assert by_sym["A"].role == "leader"
        assert by_sym["B"].role in {"laggard", "standalone"}

    def test_three_way_group(self) -> None:
        sig = [1.0, 0.5, 0.2, 0.1, 1.0]
        states = [
            _state("X", pct_change=30.0, sig=sig),
            _state("Y", pct_change=20.0, sig=sig, has_news=True),
            _state("Z", pct_change=10.0, sig=sig, has_news=True),
        ]
        result = assign_roles(states, similarity_threshold=0.7)
        by_sym = {s.symbol: s for s in result}
        assert by_sym["X"].role == "leader"
        assert by_sym["Y"].role == "laggard"
        assert by_sym["Z"].role == "laggard"

    def test_original_states_not_mutated(self) -> None:
        sig = [1.0, 0.5, 0.2, 0.1, 1.0]
        states = [_state("A", sig=sig), _state("B", sig=sig)]
        original_roles = [s.role for s in states]
        assign_roles(states, similarity_threshold=0.7)
        for s, orig in zip(states, original_roles):
            assert s.role == orig
