"""Per-ticker cumulative profit/loss stats for the scanner's prior-profit bias."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional


@dataclass
class TickerProfitStats:
    symbol: str
    cumulative_pnl: float = 0.0
    trade_count: int = 0
    win_count: int = 0

    @property
    def win_rate(self) -> float:
        """Win rate in [0, 1]; returns 0.0 when no trades have been recorded."""
        if self.trade_count == 0:
            return 0.0
        return self.win_count / self.trade_count


# Type alias matching scanner.PriorProfitLookup
PriorProfitLookup = Callable[[str], Optional[float]]


class PriorProfitTracker:
    """In-memory store of per-ticker P&L stats.

    Persistence is delegated to the caller (e.g. via the TypeScript DB layer).
    The caller can initialise this object from persisted rows at startup.
    """

    def __init__(
        self, initial_stats: Optional[dict[str, TickerProfitStats]] = None
    ) -> None:
        self._stats: dict[str, TickerProfitStats] = dict(initial_stats or {})

    # ------------------------------------------------------------------
    # Write path
    # ------------------------------------------------------------------

    def record_trade(self, symbol: str, net_pnl: float) -> TickerProfitStats:
        """Record a completed round-trip and update cumulative stats.

        net_pnl must already account for fees (i.e. is the after-cost P&L).
        Direction (long vs short) does not matter; net_pnl sign encodes the outcome.
        """
        if symbol not in self._stats:
            self._stats[symbol] = TickerProfitStats(symbol=symbol)
        stats = self._stats[symbol]
        stats.cumulative_pnl += net_pnl
        stats.trade_count += 1
        if net_pnl > 0:
            stats.win_count += 1
        return stats

    # ------------------------------------------------------------------
    # Read path
    # ------------------------------------------------------------------

    def get_stats(self, symbol: str) -> Optional[TickerProfitStats]:
        return self._stats.get(symbol)

    def all_stats(self) -> list[TickerProfitStats]:
        return list(self._stats.values())

    def as_prior_profit_lookup(self) -> PriorProfitLookup:
        """Return a callable compatible with scanner.PriorProfitLookup.

        The scanner uses this to bias the score of repeatedly profitable symbols.
        Returns the cumulative P&L for symbols with history, None otherwise.
        """
        def lookup(symbol: str) -> Optional[float]:
            stats = self._stats.get(symbol)
            return stats.cumulative_pnl if stats is not None else None

        return lookup
