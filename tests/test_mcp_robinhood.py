from dataclasses import dataclass

from trader.mcp_robinhood import REQUIRED_ROLES, _map_tools_to_roles


@dataclass
class _FakeTool:
    name: str
    description: str = ""


# The real tool list returned by Robinhood's production MCP server (agent.robinhood.com/mcp/trading).
ROBINHOOD_TOOL_NAMES = [
    "add_option_to_watchlist", "add_to_watchlist", "cancel_equity_order", "cancel_option_order",
    "create_scan", "create_watchlist", "follow_watchlist", "get_accounts", "get_earnings_calendar",
    "get_earnings_results", "get_equity_fundamentals", "get_equity_historicals", "get_equity_orders",
    "get_equity_positions", "get_equity_quotes", "get_equity_tradability", "get_index_quotes", "get_indexes",
    "get_option_chains", "get_option_historicals", "get_option_instruments", "get_option_orders",
    "get_option_positions", "get_option_quotes", "get_option_watchlist", "get_popular_watchlists",
    "get_portfolio", "get_realized_pnl", "get_scans", "get_watchlist_items", "get_watchlists",
    "place_equity_order", "place_option_order", "remove_from_watchlist", "remove_option_from_watchlist",
    "review_equity_order", "review_option_order", "run_scan", "search", "unfollow_watchlist",
    "update_scan_config", "update_scan_filters", "update_watchlist",
]

EXPECTED_ROBINHOOD_ROLE_MAP = {
    "get_account": "get_accounts",
    "get_positions": "get_equity_positions",
    "get_quote": "get_equity_quotes",
    "place_order": "place_equity_order",
    "cancel_order": "cancel_equity_order",
    "order_status": "get_equity_orders",
}


def test_maps_all_required_roles_against_real_robinhood_tool_list():
    tools = [_FakeTool(n) for n in ROBINHOOD_TOOL_NAMES]
    role_map = _map_tools_to_roles(tools)
    assert set(REQUIRED_ROLES) <= set(role_map.keys())
    assert role_map == {**role_map, **EXPECTED_ROBINHOOD_ROLE_MAP}


def test_prefers_equity_tool_over_option_variant_regardless_of_list_order():
    # Reversed order should not change which tool wins each role.
    tools = [_FakeTool(n) for n in reversed(ROBINHOOD_TOOL_NAMES)]
    role_map = _map_tools_to_roles(tools)
    for role, expected_tool in EXPECTED_ROBINHOOD_ROLE_MAP.items():
        assert role_map[role] == expected_tool


def test_name_match_outranks_misleading_description_match():
    # A fundamentals tool whose description happens to mention "quote" must
    # not steal the get_quote role from the actual quotes tool.
    tools = [_FakeTool(n) for n in ROBINHOOD_TOOL_NAMES]
    for t in tools:
        if t.name == "get_equity_fundamentals":
            t.description = "Get fundamentals including latest quote, PE ratio, and market cap."
    role_map = _map_tools_to_roles(tools)
    assert role_map["get_quote"] == "get_equity_quotes"


def test_missing_roles_are_simply_absent_not_erroring():
    tools = [_FakeTool("get_accounts"), _FakeTool("get_equity_positions")]
    role_map = _map_tools_to_roles(tools)
    assert role_map.get("get_account") == "get_accounts"
    assert "place_order" not in role_map
