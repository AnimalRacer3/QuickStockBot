"""
Handler unit tests and full RPC round-trips via MockRelaySocket.

Every protocol method is exercised against /shared schema expectations.
"""

from __future__ import annotations

import asyncio
import sqlite3
import uuid

import pytest

from bot.control.handlers import (
    handle_get_active_tickers,
    handle_get_daily_pl,
    handle_get_lists,
    handle_get_order_detail,
    handle_get_settings,
    handle_get_state,
    handle_get_ticker_detail,
    handle_get_trade_history,
    handle_subscribe_logs,
    handle_update_lists,
    handle_update_settings,
)
from bot.control.relay_client import RelayClient
from tests.control.conftest import insert_order, insert_ticker, insert_trade
from tests.control.mock_relay import MockSocketFactory

# ─── Direct handler tests ─────────────────────────────────────────────────────


class TestGetState:
    def test_returns_tickers_and_account(self, db: sqlite3.Connection) -> None:
        insert_ticker(db, symbol="TSLA")
        result = handle_get_state(db, {})
        assert isinstance(result["tickers"], list)
        assert any(t["symbol"] == "TSLA" for t in result["tickers"])
        # account may be None when no snapshot is cached
        assert "account" in result

    def test_empty_tickers(self, db: sqlite3.Connection) -> None:
        result = handle_get_state(db, {})
        assert result["tickers"] == []


class TestGetActiveTickers:
    def test_returns_symbols_list(self, db: sqlite3.Connection) -> None:
        insert_ticker(db, symbol="AAPL")
        insert_ticker(db, symbol="MSFT")
        result = handle_get_active_tickers(db, {})
        assert set(result["symbols"]) == {"AAPL", "MSFT"}


class TestGetTickerDetail:
    def test_returns_full_state_with_new_fields(self, db: sqlite3.Connection) -> None:
        insert_ticker(
            db,
            symbol="NVDA",
            rvol=4.2,
            float_shares=3_000_000,
            pct_change=12.3,
            role="leader",
        )
        result = handle_get_ticker_detail(db, {"symbol": "NVDA"})

        assert result["symbol"] == "NVDA"
        # Core ticker fields
        assert result["last_price"] >= 0
        assert "macd_line" in result
        assert "score" in result
        assert "pattern_tags" in result
        # New Section 8 fields
        assert result["rvol"] == pytest.approx(4.2)
        assert result["float_shares"] == 3_000_000
        assert result["pct_change"] == pytest.approx(12.3)
        assert result["role"] == "leader"
        assert result["tradable"] is True
        assert result["unknown_float"] is False
        assert result["macd_favorability"] is not None
        assert result["macd_eligible"] is not None

    def test_missing_ticker_raises(self, db: sqlite3.Connection) -> None:
        with pytest.raises(ValueError, match="not found"):
            handle_get_ticker_detail(db, {"symbol": "FAKE"})

    def test_missing_symbol_param_raises(self, db: sqlite3.Connection) -> None:
        with pytest.raises(ValueError, match="required"):
            handle_get_ticker_detail(db, {})


class TestGetSettings:
    def test_returns_all_required_fields(self, db: sqlite3.Connection) -> None:
        result = handle_get_settings(db, {})
        for field in (
            "bot_id",
            "relay_url",
            "license_key",
            "paper_trading",
            "broker",
            "max_positions",
            "risk_per_trade_pct",
            "daily_risk_pct",
            "risk_override_enabled",
            "goal_post_trade_count",
            "min_score",
            "auto_trade",
            "macd_fast",
            "macd_slow",
            "macd_signal",
            "log_level",
        ):
            assert field in result, f"Missing field: {field}"

    def test_goal_post_computed(self, db: sqlite3.Connection) -> None:
        result = handle_get_settings(db, {})
        daily = result["daily_risk_pct"]
        per_trade = result["risk_per_trade_pct"]
        expected = max(1, int(daily / per_trade))
        assert result["goal_post_trade_count"] == expected


class TestUpdateSettings:
    def test_basic_update_persists(self, db: sqlite3.Connection) -> None:
        result = handle_update_settings(db, {"patch": {"min_score": 70.0}})
        assert result["min_score"] == pytest.approx(70.0)

    def test_daily_target_mode_round_trips(self, db: sqlite3.Connection) -> None:
        result = handle_update_settings(db, {"patch": {"daily_target_mode": "stop"}})
        assert result["daily_target_mode"] == "stop"
        result2 = handle_update_settings(
            db, {"patch": {"daily_target_mode": "giveback"}}
        )
        assert result2["daily_target_mode"] == "giveback"

    def test_daily_giveback_pct_round_trips(self, db: sqlite3.Connection) -> None:
        result = handle_update_settings(db, {"patch": {"daily_giveback_pct": 40.0}})
        assert result["daily_giveback_pct"] == pytest.approx(40.0)

    def test_default_daily_target_mode_is_giveback(
        self, db: sqlite3.Connection
    ) -> None:
        result = handle_get_settings(db, {})
        assert result["daily_target_mode"] == "giveback"
        assert result["daily_giveback_pct"] == pytest.approx(25.0)

    def test_goal_post_returned(self, db: sqlite3.Connection) -> None:
        # Enable override and set risk values explicitly
        handle_update_settings(
            db,
            {
                "patch": {
                    "risk_override_enabled": True,
                    "daily_risk_pct": 6.0,
                    "risk_per_trade_pct": 2.0,
                }
            },
        )
        result = handle_get_settings(db, {})
        assert result["goal_post_trade_count"] == 3  # floor(6/2)

    def test_ignores_read_only_goal_post(self, db: sqlite3.Connection) -> None:
        # Sending goal_post_trade_count in patch must be silently ignored
        result = handle_update_settings(db, {"patch": {"goal_post_trade_count": 999}})
        assert result["goal_post_trade_count"] != 999


class TestGetLists:
    def test_empty_lists(self, db: sqlite3.Connection) -> None:
        result = handle_get_lists(db, {})
        assert result == {"watchlist": [], "blacklist": []}

    def test_returns_active_symbols(self, db: sqlite3.Connection) -> None:
        handle_update_lists(db, {"watchlist": ["AAPL", "TSLA"]})
        result = handle_get_lists(db, {})
        assert sorted(result["watchlist"]) == ["AAPL", "TSLA"]


class TestUpdateLists:
    def test_replace_watchlist(self, db: sqlite3.Connection) -> None:
        handle_update_lists(db, {"watchlist": ["AAPL"]})
        handle_update_lists(db, {"watchlist": ["MSFT", "NVDA"]})
        result = handle_get_lists(db, {})
        assert sorted(result["watchlist"]) == ["MSFT", "NVDA"]

    def test_independent_update(self, db: sqlite3.Connection) -> None:
        handle_update_lists(db, {"watchlist": ["AAPL"], "blacklist": ["FAKE"]})
        handle_update_lists(db, {"watchlist": ["TSLA"]})
        result = handle_get_lists(db, {})
        assert result["watchlist"] == ["TSLA"]
        assert result["blacklist"] == ["FAKE"]


class TestGetTradeHistory:
    def test_pagination(self, db: sqlite3.Connection) -> None:
        for _ in range(5):
            oid = insert_order(db)
            insert_trade(db, entry_order_id=oid)

        page1 = handle_get_trade_history(db, {"limit": 3, "offset": 0})
        page2 = handle_get_trade_history(db, {"limit": 3, "offset": 3})

        assert page1["total"] == 5
        assert len(page1["trades"]) == 3
        assert len(page2["trades"]) == 2

    def test_entry_order_embedded(self, db: sqlite3.Connection) -> None:
        oid = insert_order(db, symbol="GOOG", filled_price=10.0)
        insert_trade(db, entry_order_id=oid, symbol="GOOG")
        result = handle_get_trade_history(db, {"limit": 10, "offset": 0})
        trade = result["trades"][0]
        assert trade["entry_order"] is not None
        assert trade["entry_order"]["symbol"] == "GOOG"


class TestGetOrderDetail:
    def test_returns_order(self, db: sqlite3.Connection) -> None:
        oid = insert_order(db, symbol="NVDA", quantity=5.0)
        result = handle_get_order_detail(db, {"order_id": oid})
        assert result["id"] == oid
        assert result["symbol"] == "NVDA"
        assert result["qty"] == pytest.approx(5.0)

    def test_missing_order_raises(self, db: sqlite3.Connection) -> None:
        with pytest.raises(ValueError, match="not found"):
            handle_get_order_detail(db, {"order_id": "nonexistent"})


class TestSubscribeLogs:
    def test_returns_subscribed_true(self, db: sqlite3.Connection) -> None:
        result = handle_subscribe_logs(db, {"min_level": "info"})
        assert result == {"subscribed": True}

    def test_calls_on_subscribe(self, db: sqlite3.Connection) -> None:
        captured: list[dict] = []
        handle_subscribe_logs(
            db,
            {"categories": ["trade"], "min_level": "warning"},
            on_subscribe=captured.append,
        )
        assert captured == [{"categories": ["trade"], "min_level": "warning"}]


class TestGetDailyPL:
    def test_missing_params_raises(self, db: sqlite3.Connection) -> None:
        with pytest.raises(ValueError, match="required"):
            handle_get_daily_pl(db, {})


# ─── Full round-trip via MockRelaySocket ─────────────────────────────────────


def _make_client(db: sqlite3.Connection, factory: MockSocketFactory) -> RelayClient:
    return RelayClient(
        url="ws://mock-relay",
        bot_id="test-bot-id",
        license_key="test-license",
        connection_password="test-password",
        db=db,
        socket_factory=factory,
    )


async def _rpc_roundtrip(
    db: sqlite3.Connection,
    method: str,
    params: dict | None = None,
) -> dict:
    """
    Run one complete RPC round-trip:
    connect → auth → send request → collect response → close.
    """
    factory = MockSocketFactory()
    client = _make_client(db, factory)

    task = asyncio.create_task(client._run_session())

    # Yield so the task can run far enough to create the socket
    await asyncio.sleep(0)

    socket = factory.socket
    assert socket is not None, "Factory socket not created after task start"

    # Auth: consume the register frame
    register = await socket.pull()
    assert register["type"] == "register"

    # Send an RPC request
    req_id = str(uuid.uuid4())
    await socket.push(
        {
            "type": "rpc_request",
            "id": req_id,
            "payload": {"method": method, "params": params or {}},
        }
    )

    # Collect the response
    response = await socket.pull()
    socket.close()
    await asyncio.gather(task, return_exceptions=True)
    return response


@pytest.mark.anyio
async def test_get_state_round_trip(db: sqlite3.Connection) -> None:
    insert_ticker(db, symbol="AMZN")
    resp = await _rpc_roundtrip(db, "get_state")
    assert resp["type"] == "rpc_response"
    assert resp["payload"]["result"]["tickers"][0]["symbol"] == "AMZN"


@pytest.mark.anyio
async def test_get_active_tickers_round_trip(db: sqlite3.Connection) -> None:
    insert_ticker(db, symbol="META")
    resp = await _rpc_roundtrip(db, "get_active_tickers")
    assert "META" in resp["payload"]["result"]["symbols"]


@pytest.mark.anyio
async def test_get_ticker_detail_round_trip(db: sqlite3.Connection) -> None:
    insert_ticker(db, symbol="PLTR")
    resp = await _rpc_roundtrip(db, "get_ticker_detail", {"symbol": "PLTR"})
    assert resp["payload"]["result"]["symbol"] == "PLTR"


@pytest.mark.anyio
async def test_get_settings_round_trip(db: sqlite3.Connection) -> None:
    resp = await _rpc_roundtrip(db, "get_settings")
    result = resp["payload"]["result"]
    assert "goal_post_trade_count" in result
    assert "risk_per_trade_pct" in result


@pytest.mark.anyio
async def test_update_settings_round_trip(db: sqlite3.Connection) -> None:
    resp = await _rpc_roundtrip(db, "update_settings", {"patch": {"min_score": 55.0}})
    assert resp["payload"]["result"]["min_score"] == pytest.approx(55.0)


@pytest.mark.anyio
async def test_get_lists_round_trip(db: sqlite3.Connection) -> None:
    resp = await _rpc_roundtrip(db, "get_lists")
    result = resp["payload"]["result"]
    assert "watchlist" in result
    assert "blacklist" in result


@pytest.mark.anyio
async def test_update_lists_round_trip(db: sqlite3.Connection) -> None:
    resp = await _rpc_roundtrip(db, "update_lists", {"watchlist": ["AAPL", "TSLA"]})
    assert "AAPL" in resp["payload"]["result"]["watchlist"]


@pytest.mark.anyio
async def test_get_trade_history_round_trip(db: sqlite3.Connection) -> None:
    oid = insert_order(db)
    insert_trade(db, entry_order_id=oid)
    resp = await _rpc_roundtrip(db, "get_trade_history", {"limit": 10, "offset": 0})
    assert resp["payload"]["result"]["total"] == 1


@pytest.mark.anyio
async def test_get_order_detail_round_trip(db: sqlite3.Connection) -> None:
    oid = insert_order(db, symbol="SNOW")
    resp = await _rpc_roundtrip(db, "get_order_detail", {"order_id": oid})
    assert resp["payload"]["result"]["symbol"] == "SNOW"


@pytest.mark.anyio
async def test_subscribe_logs_round_trip(db: sqlite3.Connection) -> None:
    resp = await _rpc_roundtrip(db, "subscribe_logs", {"min_level": "info"})
    assert resp["payload"]["result"]["subscribed"] is True


@pytest.mark.anyio
async def test_get_daily_pl_round_trip(db: sqlite3.Connection) -> None:
    from bot.control.db import mark_run_day

    mark_run_day(db, "2024-01-15")
    resp = await _rpc_roundtrip(
        db, "get_daily_pl", {"start": "2024-01-15", "end": "2024-01-15"}
    )
    days = resp["payload"]["result"]["days"]
    assert len(days) == 1
    assert days[0]["date"] == "2024-01-15"


@pytest.mark.anyio
async def test_unknown_method_returns_error(db: sqlite3.Connection) -> None:
    resp = await _rpc_roundtrip(db, "nonexistent_method")
    error = resp["payload"]["error"]
    assert error["code"] == "UNKNOWN_METHOD"
