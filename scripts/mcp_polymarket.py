#!/usr/bin/env python3
"""
Polymarket MCP server
=====================

Exposes safe, typed Polymarket tools over the Model Context Protocol so any
agent / chat can query markets, orderbooks, arbitrage and wallets - and place
orders ONLY through the gated executor (paper unless DRY_RUN=false AND
LIVE_TRADING=true).

Run (stdio transport):
    python3 scripts/mcp_polymarket.py

Register in an MCP client (e.g. ~/.cursor/mcp.json or OpenClaw):
    {
      "mcpServers": {
        "polymarket": { "command": "python3", "args": ["scripts/mcp_polymarket.py"] }
      }
    }

Tools:
    list_markets, get_market, get_orderbook, find_arbitrage,
    get_wallet_positions, get_wallet_trades, rank_wallets, place_order
"""

import json
import os
import sys
from pathlib import Path

import httpx

PROJECT_ROOT = Path(__file__).parent.parent.absolute()
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

# Reuse already-tested pure logic from the agents.
from agent_arb import compute_arb  # noqa: E402
from agent_copytrader import score_wallet, rank_wallets as _rank_wallets  # noqa: E402

from mcp.server.fastmcp import FastMCP  # noqa: E402

GAMMA_API = "https://gamma-api.polymarket.com"
CLOB_API = "https://clob.polymarket.com"
DATA_API = "https://data-api.polymarket.com"
EXECUTOR_URL = os.environ.get("EXECUTOR_URL", "http://127.0.0.1:8789")
EXEC_API_TOKEN = os.environ.get("EXEC_API_TOKEN", "dev-token")
HTTP_TIMEOUT = float(os.environ.get("MCP_HTTP_TIMEOUT", "20"))

mcp = FastMCP("polymarket")


def _get(url: str, params: dict | None = None) -> object:
    with httpx.Client(timeout=HTTP_TIMEOUT) as c:
        r = c.get(url, params=params or {})
        r.raise_for_status()
        return r.json()


def _safe(value, default):
    try:
        return json.loads(value) if isinstance(value, str) else (value or default)
    except (json.JSONDecodeError, TypeError):
        return default


@mcp.tool()
def list_markets(limit: int = 20, min_liquidity: float = 0.0) -> list[dict]:
    """List trending open markets (by 24h volume), optionally filtered by liquidity."""
    data = _get(f"{GAMMA_API}/markets", {
        "closed": "false", "limit": limit, "order": "volume24hr", "ascending": "false",
    })
    out = []
    for m in data if isinstance(data, list) else []:
        liq = float(m.get("liquidity", 0) or 0)
        if liq < min_liquidity:
            continue
        prices = _safe(m.get("outcomePrices"), [])
        tokens = _safe(m.get("clobTokenIds"), [])
        out.append({
            "id": m.get("id"),
            "question": m.get("question"),
            "conditionId": m.get("conditionId"),
            "liquidity": liq,
            "yes_price": float(prices[0]) if prices else None,
            "no_price": float(prices[1]) if len(prices) > 1 else None,
            "yes_token": str(tokens[0]) if tokens else None,
            "no_token": str(tokens[1]) if len(tokens) > 1 else None,
            "negRisk": m.get("negRisk"),
            "endDate": m.get("endDate"),
        })
    return out


@mcp.tool()
def get_market(market_id: str) -> dict:
    """Get one market by numeric id or 0x condition id."""
    if market_id.startswith("0x"):
        data = _get(f"{GAMMA_API}/markets", {"condition_id": market_id})
        data = data[0] if isinstance(data, list) and data else {}
    else:
        data = _get(f"{GAMMA_API}/markets/{market_id}")
    if not data:
        return {"error": f"market not found: {market_id}"}
    prices = _safe(data.get("outcomePrices"), [])
    tokens = _safe(data.get("clobTokenIds"), [])
    return {
        "id": data.get("id"),
        "question": data.get("question"),
        "conditionId": data.get("conditionId"),
        "liquidity": float(data.get("liquidity", 0) or 0),
        "volume24h": float(data.get("volume24hr", 0) or 0),
        "yes_price": float(prices[0]) if prices else None,
        "no_price": float(prices[1]) if len(prices) > 1 else None,
        "yes_token": str(tokens[0]) if tokens else None,
        "no_token": str(tokens[1]) if len(tokens) > 1 else None,
        "negRisk": data.get("negRisk"),
        "endDate": data.get("endDate"),
        "closed": data.get("closed"),
    }


@mcp.tool()
def get_orderbook(token_id: str) -> dict:
    """Best bid/ask + top-of-book depth for a CLOB token id."""
    book = _get(f"{CLOB_API}/book", {"token_id": token_id})
    bids = book.get("bids", []) if isinstance(book, dict) else []
    asks = book.get("asks", []) if isinstance(book, dict) else []
    best_bid = max((float(b["price"]) for b in bids), default=None)
    best_ask = min((float(a["price"]) for a in asks), default=None)
    spread = (best_ask - best_bid) if (best_bid is not None and best_ask is not None) else None
    return {
        "token_id": token_id,
        "best_bid": best_bid,
        "best_ask": best_ask,
        "spread": round(spread, 4) if spread is not None else None,
        "bid_levels": len(bids),
        "ask_levels": len(asks),
    }


@mcp.tool()
def find_arbitrage(limit: int = 60, fee_pct: float = 0.02) -> list[dict]:
    """Scan NegRisk multi-outcome events for sum-to-one arbitrage (snapshot/mid prices).

    Returns events whose summed outcome prices imply positive net edge after fees.
    """
    events = _get(f"{GAMMA_API}/events", {
        "closed": "false", "limit": limit, "order": "volume24hr", "ascending": "false",
    })
    out = []
    for ev in events if isinstance(events, list) else []:
        if not (ev.get("negRisk") or ev.get("enableNegRisk")):
            continue
        markets = ev.get("markets", []) or []
        if len(markets) < 3:
            continue
        yes = []
        ok = True
        for m in markets:
            if m.get("closed") or not m.get("active", True):
                ok = False
                break
            prices = _safe(m.get("outcomePrices"), [])
            try:
                yes.append(float(prices[0]))
            except (ValueError, IndexError):
                ok = False
                break
        if not ok or len(yes) < 3:
            continue
        analysis = compute_arb(yes, size_usd=100, fee_pct=fee_pct)
        if analysis and analysis["profitable"]:
            out.append({
                "event": ev.get("title"),
                "slug": ev.get("slug"),
                "n_outcomes": analysis["n_outcomes"],
                "sum_price": analysis["sum_ask"],
                "net_edge_pct": analysis["net_pct"],
                "liquidity": float(ev.get("liquidity", 0) or 0),
            })
    return out


@mcp.tool()
def get_wallet_positions(wallet: str, limit: int = 50) -> list[dict]:
    """Open/closed positions for a wallet (with PnL) from the public Data API."""
    data = _get(f"{DATA_API}/positions", {"user": wallet, "limit": limit})
    return data if isinstance(data, list) else []


@mcp.tool()
def get_wallet_trades(wallet: str, limit: int = 20) -> list[dict]:
    """Recent trades for a wallet from the public Data API."""
    data = _get(f"{DATA_API}/trades", {"user": wallet, "limit": limit})
    return data if isinstance(data, list) else []


@mcp.tool()
def rank_wallets(wallets: list[str]) -> list[dict]:
    """Rank wallets by ROI/winrate/PnL using their public positions."""
    wallet_positions = {}
    for w in wallets:
        try:
            wallet_positions[w] = _get(f"{DATA_API}/positions", {"user": w, "limit": 100})
        except Exception:  # noqa: BLE001
            wallet_positions[w] = []
    return _rank_wallets(wallet_positions)


@mcp.tool()
def place_order(market_id: str, outcome: str = "YES", side: str = "buy",
                size_usd: float = 5.0, max_price: float = 0.5) -> dict:
    """Place an order via the gated executor.

    SAFE BY DESIGN: the executor only sends a real on-chain order when
    DRY_RUN=false AND LIVE_TRADING=true; otherwise it returns a simulated order.
    """
    payload = {
        "marketId": market_id, "outcomeId": outcome, "side": side,
        "sizeUsd": size_usd, "maxPrice": max_price,
    }
    try:
        with httpx.Client(timeout=HTTP_TIMEOUT) as c:
            r = c.post(f"{EXECUTOR_URL}/order", json=payload,
                       headers={"Authorization": f"Bearer {EXEC_API_TOKEN}"})
            return {"status_code": r.status_code, "response": r.json()}
    except Exception as e:  # noqa: BLE001
        return {"error": f"executor unreachable at {EXECUTOR_URL}: {e}"}


if __name__ == "__main__":
    mcp.run()
