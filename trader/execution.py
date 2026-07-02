"""Order execution: real orders through the Robinhood MCP client in LIVE mode,
pessimistic simulated fills in DRY_RUN. Robinhood MCP is the source of the
pre-order quote sanity-check in both modes (it's authoritative for execution).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from trader.mcp_robinhood import RobinhoodMCPClient

logger = logging.getLogger("trader.execution")


class ExecutionError(Exception):
    pass


@dataclass(frozen=True)
class Quote:
    bid: float
    ask: float

    @property
    def mid(self) -> float:
        return (self.bid + self.ask) / 2.0


@dataclass(frozen=True)
class FillResult:
    fill_price: float
    slippage: float
    order_id: str | None
    timestamp: datetime
    simulated: bool


_BID_KEYS = ("bid_price", "bid", "bidPrice")
_ASK_KEYS = ("ask_price", "ask", "askPrice")


def _first_present(payload: dict[str, Any], keys: tuple[str, ...]) -> float | None:
    for key in keys:
        if key in payload and payload[key] is not None:
            try:
                return float(payload[key])
            except (TypeError, ValueError):
                continue
    return None


def parse_quote(payload: dict[str, Any]) -> Quote:
    bid = _first_present(payload, _BID_KEYS)
    ask = _first_present(payload, _ASK_KEYS)
    if bid is None or ask is None:
        raise ExecutionError(f"Could not parse bid/ask from quote payload: {payload!r}")
    return Quote(bid=bid, ask=ask)


class ExecutionEngine:
    """Places (or simulates) buy/sell orders. `mode` is "DRY_RUN" or "LIVE"."""

    def __init__(self, mode: str, mcp_client: RobinhoodMCPClient, order_poll_timeout: float = 30.0):
        self.mode = mode.upper()
        self.mcp = mcp_client
        self.order_poll_timeout = order_poll_timeout

    def get_quote(self, ticker: str) -> Quote:
        payload = self.mcp.get_quote(ticker)
        return parse_quote(payload)

    def enter_long(self, ticker: str, qty: int) -> FillResult:
        quote = self.get_quote(ticker)  # fresh sanity-check quote immediately before the order
        if self.mode == "DRY_RUN":
            return self._simulate_fill(quote.ask, quote)
        return self._place_live_order(ticker, qty, side="buy", reference_price=quote.ask)

    def exit_long(self, ticker: str, qty: int) -> FillResult:
        quote = self.get_quote(ticker)
        if self.mode == "DRY_RUN":
            return self._simulate_fill(quote.bid, quote)
        return self._place_live_order(ticker, qty, side="sell", reference_price=quote.bid)

    def _simulate_fill(self, fill_price: float, quote: Quote) -> FillResult:
        slippage = quote.ask - quote.bid  # the spread, logged as the DRY_RUN slippage cost
        return FillResult(
            fill_price=fill_price,
            slippage=slippage,
            order_id=None,
            timestamp=datetime.now(timezone.utc),
            simulated=True,
        )

    def _place_live_order(self, ticker: str, qty: int, side: str, reference_price: float) -> FillResult:
        order = self.mcp.place_order(ticker, side=side, qty=qty, order_type="market")
        order_id = str(order.get("order_id") or order.get("id") or "")
        if not order_id:
            raise ExecutionError(f"place_order for {ticker} did not return an order id: {order!r}")

        filled_price = self._await_fill(order_id)
        slippage = abs(filled_price - reference_price)
        return FillResult(
            fill_price=filled_price,
            slippage=slippage,
            order_id=order_id,
            timestamp=datetime.now(timezone.utc),
            simulated=False,
        )

    def _await_fill(self, order_id: str) -> float:
        deadline = time.monotonic() + self.order_poll_timeout
        while time.monotonic() < deadline:
            status = self.mcp.order_status(order_id)
            state = str(status.get("status", "")).lower()
            if state in ("filled", "complete", "completed"):
                filled_price = status.get("filled_avg_price") or status.get("average_price") or status.get("price")
                if filled_price is None:
                    raise ExecutionError(f"Order {order_id} filled but no fill price returned: {status!r}")
                return float(filled_price)
            if state in ("rejected", "cancelled", "canceled", "failed"):
                raise ExecutionError(f"Order {order_id} did not fill: status={state}")
            time.sleep(1.0)
        raise ExecutionError(f"Order {order_id} did not fill within {self.order_poll_timeout}s")


class ReplayExecutionEngine:
    """Fills against recorded candle closes for `--replay` -- no MCP connection
    available offline, so quotes are synthesized with a small fixed spread."""

    def __init__(self, synthetic_spread_pct: float = 0.05):
        self.synthetic_spread_pct = synthetic_spread_pct
        self._last_price: dict[str, float] = {}

    def set_last_price(self, ticker: str, price: float) -> None:
        self._last_price[ticker] = price

    def _quote_for(self, ticker: str) -> Quote:
        price = self._last_price.get(ticker)
        if price is None:
            raise ExecutionError(f"No replay price recorded yet for {ticker}")
        half_spread = price * (self.synthetic_spread_pct / 100.0) / 2.0
        return Quote(bid=price - half_spread, ask=price + half_spread)

    def enter_long(self, ticker: str, qty: int) -> FillResult:
        quote = self._quote_for(ticker)
        return FillResult(
            fill_price=quote.ask, slippage=quote.ask - quote.bid, order_id=None,
            timestamp=datetime.now(timezone.utc), simulated=True,
        )

    def exit_long(self, ticker: str, qty: int) -> FillResult:
        quote = self._quote_for(ticker)
        return FillResult(
            fill_price=quote.bid, slippage=quote.ask - quote.bid, order_id=None,
            timestamp=datetime.now(timezone.utc), simulated=True,
        )
