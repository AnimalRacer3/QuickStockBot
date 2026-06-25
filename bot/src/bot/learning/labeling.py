"""Label assignment for completed round-trip trades."""

from __future__ import annotations


def label_from_pnl(net_pnl: float) -> int:
    """Map net P&L to a binary label.

    Returns:
        1 (good) when net_pnl > 0, 0 (bad) otherwise.

    Works identically for long trades (buy→sell) and short trades (short→buy):
    the caller is responsible for computing net_pnl with the correct sign.
    """
    return 1 if net_pnl > 0 else 0


def trade_label_str(net_pnl: float) -> str:
    """Return the string label used in the trades table ("good" / "bad")."""
    return "good" if net_pnl > 0 else "bad"
