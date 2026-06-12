"""MCP protocol handshake test for scripts/mcp_polymarket.py.

Spawns the server over stdio, initializes the session and lists tools.
This proves it is a valid MCP server exposing the expected tools (no network).

Run: python3 -m pytest tests/test_mcp_polymarket.py -v
"""

import asyncio
from pathlib import Path

import pytest

SERVER = Path(__file__).parent.parent / "scripts" / "mcp_polymarket.py"

EXPECTED_TOOLS = {
    "list_markets", "get_market", "get_orderbook", "find_arbitrage",
    "get_wallet_positions", "get_wallet_trades", "rank_wallets", "place_order",
}


async def _list_tool_names() -> set:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    params = StdioServerParameters(command="python3", args=[str(SERVER)])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            return {t.name for t in tools.tools}


def test_mcp_server_lists_expected_tools():
    try:
        import mcp  # noqa: F401
    except ImportError:
        pytest.skip("mcp SDK not installed")
    names = asyncio.run(asyncio.wait_for(_list_tool_names(), timeout=30))
    assert EXPECTED_TOOLS.issubset(names), f"missing tools: {EXPECTED_TOOLS - names}"
