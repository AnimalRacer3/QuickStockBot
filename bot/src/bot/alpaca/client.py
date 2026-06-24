from __future__ import annotations

import time
from abc import ABC, abstractmethod
from datetime import datetime
from decimal import Decimal
from typing import Optional

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from bot.alpaca.config import AlpacaConfig
from bot.models import (
    AccountSnapshot,
    Asset,
    Bar,
    NewsItem,
    Order,
    OrderSide,
    OrderStatus,
    OrderType,
    Position,
    Quote,
    TimeInForce,
)


class CalendarDay:
    """Minimal representation of a single trading day from Alpaca's calendar."""

    __slots__ = ("date", "open", "close")

    def __init__(self, date: str, open_: str, close: str) -> None:
        self.date = date    # "YYYY-MM-DD"
        self.open = open_   # "HH:MM" Eastern
        self.close = close  # "HH:MM" Eastern


class ClockInfo:
    """Current market clock from Alpaca."""

    __slots__ = ("timestamp", "is_open", "next_open", "next_close")

    def __init__(
        self,
        timestamp: str,
        is_open: bool,
        next_open: str,
        next_close: str,
    ) -> None:
        self.timestamp = timestamp
        self.is_open = is_open
        self.next_open = next_open
        self.next_close = next_close


class MarketClient(ABC):
    """Interface for all market/broker interactions."""

    @abstractmethod
    def get_calendar(self, start: str, end: str) -> list[CalendarDay]: ...

    @abstractmethod
    def get_clock(self) -> ClockInfo: ...

    @abstractmethod
    def get_bars(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        timeframe: str = "1Min",
        limit: int = 1000,
    ) -> list[Bar]: ...

    @abstractmethod
    def get_latest_quote(self, symbol: str) -> Quote: ...

    @abstractmethod
    def get_latest_price(self, symbol: str) -> Decimal: ...

    @abstractmethod
    def list_assets(self) -> list[Asset]: ...

    @abstractmethod
    def get_news(
        self,
        symbols: list[str],
        limit: int = 10,
    ) -> list[NewsItem]: ...

    @abstractmethod
    def submit_order(
        self,
        symbol: str,
        qty: Decimal,
        side: OrderSide,
        order_type: OrderType,
        time_in_force: TimeInForce = TimeInForce.DAY,
        limit_price: Optional[Decimal] = None,
    ) -> Order: ...

    @abstractmethod
    def get_order(self, order_id: str) -> Order: ...

    @abstractmethod
    def poll_order(
        self,
        order_id: str,
        timeout_seconds: float = 60.0,
        poll_interval: float = 1.0,
    ) -> Order: ...

    @abstractmethod
    def list_positions(self) -> list[Position]: ...

    @abstractmethod
    def get_account(self) -> AccountSnapshot: ...


def _is_transient(exc: BaseException) -> bool:
    if isinstance(exc, httpx.TimeoutException):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in {429, 500, 502, 503, 504}
    return False


class AlpacaClient(MarketClient):
    def __init__(
        self, config: AlpacaConfig, http_client: Optional[httpx.Client] = None
    ) -> None:
        self._cfg = config
        self._http = http_client or httpx.Client(
            headers={
                "APCA-API-KEY-ID": config.api_key,
                "APCA-API-SECRET-KEY": config.secret_key,
            },
            timeout=30.0,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _broker_get(self, path: str, **params: object) -> dict:  # type: ignore[type-arg]
        return self._get(self._cfg.base_url, path, **params)

    def _broker_post(self, path: str, body: dict) -> dict:  # type: ignore[type-arg]
        return self._post(self._cfg.base_url, path, body)

    def _data_get(self, path: str, **params: object) -> dict:  # type: ignore[type-arg]
        return self._get(self._cfg.data_url, path, **params)

    @retry(
        retry=retry_if_exception(_is_transient),
        wait=wait_exponential(multiplier=1, min=1, max=16),
        stop=stop_after_attempt(4),
        reraise=True,
    )
    def _get(self, base: str, path: str, **params: object) -> dict:  # type: ignore[type-arg]
        clean_params = {k: v for k, v in params.items() if v is not None}
        resp = self._http.get(f"{base}{path}", params=clean_params)  # type: ignore[arg-type]
        resp.raise_for_status()
        return resp.json()

    @retry(
        retry=retry_if_exception(_is_transient),
        wait=wait_exponential(multiplier=1, min=1, max=16),
        stop=stop_after_attempt(4),
        reraise=True,
    )
    def _post(self, base: str, path: str, body: dict) -> dict:  # type: ignore[type-arg]
        resp = self._http.post(f"{base}{path}", json=body)
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # Mapping helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _map_bar(symbol: str, raw: dict, timeframe: str) -> Bar:  # type: ignore[type-arg]
        return Bar(
            symbol=symbol,
            timestamp=raw["t"],
            open=Decimal(str(raw["o"])),
            high=Decimal(str(raw["h"])),
            low=Decimal(str(raw["l"])),
            close=Decimal(str(raw["c"])),
            volume=int(raw["v"]),
            vwap=Decimal(str(raw["vw"])) if raw.get("vw") is not None else None,
            trade_count=raw.get("n"),
            timeframe=timeframe,
        )

    @staticmethod
    def _map_quote(symbol: str, raw: dict) -> Quote:  # type: ignore[type-arg]
        return Quote(
            symbol=symbol,
            timestamp=raw["t"],
            bid_price=Decimal(str(raw["bp"])),
            bid_size=int(raw["bs"]),
            ask_price=Decimal(str(raw["ap"])),
            ask_size=int(raw["as"]),
        )

    @staticmethod
    def _map_asset(raw: dict) -> Asset:  # type: ignore[type-arg]
        return Asset(
            id=raw["id"],
            symbol=raw["symbol"],
            name=raw.get("name", ""),
            exchange=raw.get("exchange", ""),
            asset_class=raw.get("class", ""),
            tradable=bool(raw.get("tradable", False)),
            marginable=bool(raw.get("marginable", False)),
            shortable=bool(raw.get("shortable", False)),
            easy_to_borrow=bool(raw.get("easy_to_borrow", False)),
            fractionable=bool(raw.get("fractionable", False)),
        )

    @staticmethod
    def _map_news(raw: dict) -> NewsItem:  # type: ignore[type-arg]
        return NewsItem(
            id=int(raw["id"]),
            headline=raw["headline"],
            summary=raw.get("summary", ""),
            author=raw.get("author", ""),
            created_at=raw["created_at"],
            updated_at=raw["updated_at"],
            url=raw.get("url", ""),
            symbols=raw.get("symbols", []),
            source=raw.get("source", ""),
        )

    @staticmethod
    def _map_order(raw: dict) -> Order:  # type: ignore[type-arg]
        return Order(
            id=raw["id"],
            client_order_id=raw["client_order_id"],
            symbol=raw["symbol"],
            side=OrderSide(raw["side"]),
            order_type=OrderType(raw["type"]),
            qty=Decimal(str(raw["qty"])),
            filled_qty=Decimal(str(raw.get("filled_qty") or "0")),
            limit_price=Decimal(str(raw["limit_price"]))
            if raw.get("limit_price")
            else None,
            status=OrderStatus(raw["status"]),
            time_in_force=TimeInForce(raw["time_in_force"]),
            submitted_at=raw["submitted_at"],
            filled_at=raw.get("filled_at"),
            canceled_at=raw.get("canceled_at"),
            expired_at=raw.get("expired_at"),
            filled_avg_price=(
                Decimal(str(raw["filled_avg_price"]))
                if raw.get("filled_avg_price")
                else None
            ),
        )

    @staticmethod
    def _map_position(raw: dict) -> Position:  # type: ignore[type-arg]
        return Position(
            symbol=raw["symbol"],
            qty=Decimal(str(raw["qty"])),
            avg_entry_price=Decimal(str(raw["avg_entry_price"])),
            market_value=Decimal(str(raw["market_value"])),
            unrealized_pl=Decimal(str(raw["unrealized_pl"])),
            unrealized_plpc=Decimal(str(raw["unrealized_plpc"])),
            current_price=Decimal(str(raw["current_price"])),
            side=raw["side"],
        )

    @staticmethod
    def _map_account(raw: dict) -> AccountSnapshot:  # type: ignore[type-arg]
        equity = Decimal(str(raw["equity"]))
        is_pdt = bool(raw.get("pattern_day_trader", False))
        pdt_restricted = is_pdt and equity < Decimal("25000")
        return AccountSnapshot(
            buying_power=Decimal(str(raw["buying_power"])),
            equity=equity,
            cash=Decimal(str(raw["cash"])),
            portfolio_value=Decimal(str(raw["portfolio_value"])),
            pattern_day_trader=is_pdt,
            day_trade_count=int(raw.get("daytrade_count", 0)),
            day_trading_buying_power=Decimal(
                str(raw.get("daytrading_buying_power", "0"))
            ),
            is_pdt_restricted=pdt_restricted,
        )

    # ------------------------------------------------------------------
    # MarketClient implementation
    # ------------------------------------------------------------------

    def get_bars(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        timeframe: str = "1Min",
        limit: int = 1000,
    ) -> list[Bar]:
        data = self._data_get(
            f"/v2/stocks/{symbol}/bars",
            timeframe=timeframe,
            start=start.isoformat(),
            end=end.isoformat(),
            limit=limit,
            feed="iex",
        )
        return [self._map_bar(symbol, b, timeframe) for b in data.get("bars", [])]

    def get_latest_quote(self, symbol: str) -> Quote:
        data = self._data_get(f"/v2/stocks/{symbol}/quotes/latest", feed="iex")
        return self._map_quote(symbol, data["quote"])

    def get_latest_price(self, symbol: str) -> Decimal:
        return self.get_latest_quote(symbol).mid_price

    def list_assets(self) -> list[Asset]:
        data = self._broker_get(
            "/v2/assets",
            status="active",
            asset_class="us_equity",
        )
        return [self._map_asset(a) for a in data]

    def get_news(self, symbols: list[str], limit: int = 10) -> list[NewsItem]:
        data = self._data_get(
            "/v1beta1/news",
            symbols=",".join(symbols),
            limit=limit,
        )
        return [self._map_news(n) for n in data.get("news", [])]

    def submit_order(
        self,
        symbol: str,
        qty: Decimal,
        side: OrderSide,
        order_type: OrderType,
        time_in_force: TimeInForce = TimeInForce.DAY,
        limit_price: Optional[Decimal] = None,
    ) -> Order:
        body: dict = {  # type: ignore[type-arg]
            "symbol": symbol,
            "qty": str(qty),
            "side": side.value,
            "type": order_type.value,
            "time_in_force": time_in_force.value,
        }
        if limit_price is not None:
            body["limit_price"] = str(limit_price)
        raw = self._broker_post("/v2/orders", body)
        return self._map_order(raw)

    def get_order(self, order_id: str) -> Order:
        raw = self._broker_get(f"/v2/orders/{order_id}")
        return self._map_order(raw)

    def poll_order(
        self,
        order_id: str,
        timeout_seconds: float = 60.0,
        poll_interval: float = 1.0,
    ) -> Order:
        deadline = time.monotonic() + timeout_seconds
        while True:
            order = self.get_order(order_id)
            if order.status in {
                OrderStatus.FILLED,
                OrderStatus.CANCELED,
                OrderStatus.EXPIRED,
                OrderStatus.REJECTED,
            }:
                return order
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"Order {order_id} did not reach terminal status within "
                    f"{timeout_seconds}s; last status: {order.status}"
                )
            time.sleep(poll_interval)

    def list_positions(self) -> list[Position]:
        data = self._broker_get("/v2/positions")
        return [self._map_position(p) for p in data]

    def get_account(self) -> AccountSnapshot:
        raw = self._broker_get("/v2/account")
        return self._map_account(raw)

    def get_calendar(self, start: str, end: str) -> list[CalendarDay]:
        data = self._broker_get("/v2/calendar", start=start, end=end)
        return [
            CalendarDay(d["date"], d["open"], d["close"])
            for d in (data if isinstance(data, list) else [])
        ]

    def get_clock(self) -> ClockInfo:
        raw = self._broker_get("/v2/clock")
        return ClockInfo(
            timestamp=raw["timestamp"],
            is_open=bool(raw.get("is_open", False)),
            next_open=raw.get("next_open", ""),
            next_close=raw.get("next_close", ""),
        )
