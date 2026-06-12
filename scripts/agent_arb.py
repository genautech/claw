#!/usr/bin/env python3
"""
ArbAgent - Real sum-to-one / NegRisk arbitrage detector (paper-first)
=====================================================================

Replaces the random/simulated signal stubs with a mathematically grounded
arbitrage detector for Polymarket:

- Binary sum-to-one:  ask(YES) + ask(NO) < 1 - costs  -> buy both, lock $1.
- Multi-outcome NegRisk:  sum(ask(outcome_i)) < 1 - costs  -> buy all outcomes.

Modes:
  --mode snapshot   One-shot scan via Gamma API (NegRisk events use mid prices;
                    good for breadth, approximate). Default.
  --mode stream     Real-time scan via CLOB WebSocket (true best asks) for a set
                    of binary markets, for --duration seconds.

Safety: detection-only / paper. It NEVER sends a real order. Live execution is
gated behind DRY_RUN=false AND LIVE_TRADING=true (and is intentionally not
implemented here yet - see scripts/polymarket-exec.py).

Output: data/arb_opportunities.jsonl  (one JSON object per detected opportunity)
"""

import argparse
import asyncio
import json
import logging
import os
import ssl
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx

PROJECT_ROOT = Path(__file__).parent.parent.absolute()
DATA_DIR = PROJECT_ROOT / "data"
OPP_FILE = DATA_DIR / "arb_opportunities.jsonl"

GAMMA_API_BASE = "https://gamma-api.polymarket.com"
WS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"

logger = logging.getLogger("ArbAgent")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# ---------------------------------------------------------------------------
# Config (env-overridable). Costs are what separate a real edge from noise.
# ---------------------------------------------------------------------------
DRY_RUN = os.environ.get("DRY_RUN", "true").lower() == "true"
LIVE_TRADING = os.environ.get("LIVE_TRADING", "false").lower() == "true"

FEE_PCT = float(os.environ.get("ARB_FEE_PCT", "0.02"))          # 2% winner fee
GAS_USD = float(os.environ.get("ARB_GAS_USD", "0.10"))          # ~2 legs of Polygon gas
EDGE_BUFFER_PCT = float(os.environ.get("ARB_EDGE_BUFFER_PCT", "0.005"))  # 0.5% safety
MIN_LIQUIDITY_USD = float(os.environ.get("ARB_MIN_LIQUIDITY_USD", "10000"))
MAX_POSITION_USD = float(os.environ.get("ARB_MAX_POSITION_USD", "50"))
CAPITAL_USD = float(os.environ.get("CAPITAL_USD", "1000"))
KELLY_FRACTION = float(os.environ.get("ARB_KELLY_FRACTION", "0.25"))
FILL_RATE_ASSUMED = float(os.environ.get("ARB_FILL_RATE", "0.5"))  # 40-70% per research
MAX_GROUPS = int(os.environ.get("ARB_MAX_GROUPS", "40"))


def is_live() -> bool:
    """Real trading requires dry-run OFF and the explicit live gate OPEN."""
    return (not DRY_RUN) and LIVE_TRADING


# ===========================================================================
# Pure functions (no I/O) - unit tested in tests/test_arb_math.py
# ===========================================================================

def best_ask_from_book(asks: list) -> Optional[float]:
    """Best ask = lowest price someone is willing to sell at (price you pay to buy).

    Robust to either sort order in the orderbook payload.
    """
    prices = []
    for a in asks or []:
        try:
            prices.append(float(a["price"]))
        except (KeyError, TypeError, ValueError):
            continue
    return min(prices) if prices else None


def compute_arb(
    ask_prices: list[float],
    size_usd: float,
    fee_pct: float = FEE_PCT,
    gas_usd: float = GAS_USD,
    buffer_pct: float = EDGE_BUFFER_PCT,
) -> Optional[dict]:
    """Compute net arbitrage edge for buying one share of every mutually-exclusive
    outcome (binary => 2 prices, NegRisk => N prices).

    Buying a full set costs `sum(ask_prices)` and pays exactly $1 at resolution
    (or via merge+redeem). Returns an analysis dict, or None if inputs invalid.

    net_pct is profit relative to deployed size, AFTER the winner fee, gas, and a
    safety buffer. `profitable` is True only when net_pct clears the buffer.
    """
    if not ask_prices or any(p is None for p in ask_prices):
        return None
    if size_usd <= 0:
        return None
    sum_ask = float(sum(ask_prices))
    if sum_ask <= 0:
        return None

    sets = size_usd / sum_ask          # number of $1-paying sets we can buy
    payout = sets * 1.0                 # $1 per set at resolution
    gross_profit = payout - size_usd    # = sets * (1 - sum_ask)
    fee = fee_pct * payout              # winner fee applies to the $1 payout
    net_usd = gross_profit - fee - gas_usd
    net_pct = net_usd / size_usd

    return {
        "sum_ask": round(sum_ask, 6),
        "n_outcomes": len(ask_prices),
        "sets": round(sets, 4),
        "gross_profit_usd": round(gross_profit, 4),
        "fee_usd": round(fee, 4),
        "gas_usd": round(gas_usd, 4),
        "net_usd": round(net_usd, 4),
        "net_pct": round(net_pct, 5),
        "profitable": net_pct > buffer_pct,
    }


def fractional_kelly_size(
    net_pct: float,
    capital: float = CAPITAL_USD,
    fraction: float = KELLY_FRACTION,
    max_position: float = MAX_POSITION_USD,
) -> float:
    """Conservative sizing for near-risk-free arb.

    Pure sum-to-one arb has ~no downside, so 'full Kelly' would be unbounded;
    we instead deploy a fraction of capital, capped by max_position, and only
    when the edge is positive.
    """
    if net_pct <= 0:
        return 0.0
    return round(min(max_position, capital * fraction), 2)


# ===========================================================================
# I/O helpers
# ===========================================================================

def log_opportunity(opp: dict) -> None:
    """Append one opportunity record to the JSONL (falls back to /tmp)."""
    try:
        DATA_DIR.mkdir(exist_ok=True)
        with open(OPP_FILE, "a") as f:
            f.write(json.dumps(opp) + "\n")
    except PermissionError:
        with open(Path("/tmp/arb_opportunities.jsonl"), "a") as f:
            f.write(json.dumps(opp) + "\n")


def _safe_json(value, default):
    try:
        return json.loads(value) if isinstance(value, str) else (value or default)
    except (json.JSONDecodeError, TypeError):
        return default


def _days_to_resolution(end_date: str) -> Optional[float]:
    if not end_date:
        return None
    try:
        end = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
        return (end - datetime.now(timezone.utc)).total_seconds() / 86400.0
    except ValueError:
        return None


def build_opportunity(kind: str, group_id: str, question: str,
                      tokens: list[str], asks: list[float], source: str,
                      cumulative_holder: dict) -> Optional[dict]:
    """Run the arb math and, if profitable, build + accumulate a paper record."""
    size = fractional_kelly_size(0.01)  # provisional; recomputed once we know edge
    analysis = compute_arb(asks, size_usd=max(size, 1.0))
    if not analysis or not analysis["profitable"]:
        return None

    size = fractional_kelly_size(analysis["net_pct"])
    analysis = compute_arb(asks, size_usd=max(size, 1.0)) or analysis
    paper_pnl = round(analysis["net_usd"] * FILL_RATE_ASSUMED, 4)
    cumulative_holder["pnl"] = round(cumulative_holder.get("pnl", 0.0) + paper_pnl, 4)

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "type": kind,
        "group_id": group_id,
        "question": question[:140],
        "tokens": [t[:18] for t in tokens],
        "asks": [round(a, 4) for a in asks],
        "sum_ask": analysis["sum_ask"],
        "n_outcomes": analysis["n_outcomes"],
        "size_usd": round(size, 2),
        "net_edge_usd": analysis["net_usd"],
        "net_edge_pct": analysis["net_pct"],
        "fee_usd": analysis["fee_usd"],
        "gas_usd": analysis["gas_usd"],
        "fill_rate_assumed": FILL_RATE_ASSUMED,
        "paper_pnl": paper_pnl,
        "cumulative_paper_pnl": cumulative_holder["pnl"],
        "source": source,
        "dry_run": DRY_RUN,
        "executed": False,  # paper: never sends a real order
    }


# ===========================================================================
# Snapshot mode (Gamma API) - breadth scan, NegRisk multi-outcome via mid price
# ===========================================================================

async def scan_snapshot() -> dict:
    """Scan NegRisk multi-outcome events + binary markets via Gamma snapshot.

    NegRisk events: sum of per-candidate YES (mid) prices < 1 - costs is a real
    multi-outcome arb signal (mid sum can drift from 1). Binary markets on mid
    prices will (correctly) almost never flag - true binary arb only shows on the
    ask side (use --mode stream for that).
    """
    found = 0
    cumulative = {"pnl": 0.0}
    async with httpx.AsyncClient(timeout=30.0) as http:
        # --- Multi-outcome NegRisk events ---
        resp = await http.get(
            f"{GAMMA_API_BASE}/events",
            params={"closed": "false", "limit": 60, "order": "volume24hr", "ascending": "false"},
        )
        resp.raise_for_status()
        events = resp.json()
        for ev in events:
            markets = ev.get("markets", []) or []
            if len(markets) < 3:
                continue  # need a real multi-outcome set
            # Only NegRisk events are mutually exclusive (exactly one outcome wins),
            # so summing their YES prices is meaningful. Non-NegRisk events just
            # bundle independent props and must NOT be summed as one arb set.
            if not (ev.get("negRisk") or ev.get("enableNegRisk")):
                continue
            yes_prices, tokens = [], []
            for m in markets:
                if m.get("closed") or not m.get("active", True):
                    yes_prices = []
                    break
                prices = _safe_json(m.get("outcomePrices"), [])
                toks = _safe_json(m.get("clobTokenIds"), [])
                if not prices or not toks:
                    yes_prices = []
                    break
                try:
                    yes_prices.append(float(prices[0]))
                    tokens.append(str(toks[0]))
                except (ValueError, IndexError):
                    yes_prices = []
                    break
            if not yes_prices or len(yes_prices) < 3:
                continue
            opp = build_opportunity(
                "negrisk_multi_outcome",
                ev.get("slug", ev.get("id", "?")),
                ev.get("title", "?"),
                tokens, yes_prices,
                "gamma_snapshot_mid",
                cumulative,
            )
            if opp:
                opp["liquidity_usd"] = float(ev.get("liquidity", 0) or 0)
                log_opportunity(opp)
                found += 1
                logger.info(
                    f"\U0001f3af NEGRISK ARB: {opp['question'][:50]!r} "
                    f"sum={opp['sum_ask']} net={opp['net_edge_pct']*100:.2f}% "
                    f"(paper PnL +${opp['paper_pnl']})"
                )

        # --- Binary markets (mid) ---
        resp = await http.get(
            f"{GAMMA_API_BASE}/markets",
            params={"closed": "false", "limit": 200, "order": "volume24hr", "ascending": "false"},
        )
        resp.raise_for_status()
        scanned = 0
        for m in resp.json():
            if float(m.get("liquidity", 0) or 0) < MIN_LIQUIDITY_USD:
                continue
            prices = _safe_json(m.get("outcomePrices"), [])
            toks = _safe_json(m.get("clobTokenIds"), [])
            if len(prices) != 2 or len(toks) != 2:
                continue
            scanned += 1
            try:
                asks = [float(prices[0]), float(prices[1])]
            except ValueError:
                continue
            opp = build_opportunity(
                "binary_sum_to_one",
                m.get("conditionId", m.get("id", "?")),
                m.get("question", "?"),
                [str(toks[0]), str(toks[1])], asks,
                "gamma_snapshot_mid",
                cumulative,
            )
            if opp:
                log_opportunity(opp)
                found += 1
                logger.info(
                    f"\U0001f3af BINARY ARB: {opp['question'][:50]!r} "
                    f"sum={opp['sum_ask']} net={opp['net_edge_pct']*100:.2f}%"
                )

    return {"found": found, "cumulative_paper_pnl": cumulative["pnl"], "binary_scanned": scanned}


# ===========================================================================
# Stream mode (CLOB WebSocket) - real best asks, binary sum-to-one
# ===========================================================================

async def _select_binary_groups(limit: int) -> list[dict]:
    """Pick liquid, soon-resolving binary markets and return {tokens, question}."""
    groups = []
    async with httpx.AsyncClient(timeout=30.0) as http:
        resp = await http.get(
            f"{GAMMA_API_BASE}/markets",
            params={"closed": "false", "limit": 300, "order": "volume24hr", "ascending": "false"},
        )
        resp.raise_for_status()
        for m in resp.json():
            if float(m.get("liquidity", 0) or 0) < MIN_LIQUIDITY_USD:
                continue
            toks = _safe_json(m.get("clobTokenIds"), [])
            if len(toks) != 2:
                continue
            groups.append({
                "group_id": m.get("conditionId", m.get("id", "?")),
                "question": m.get("question", "?"),
                "tokens": [str(toks[0]), str(toks[1])],
            })
            if len(groups) >= limit:
                break
    return groups


async def scan_stream(duration: int) -> dict:
    """Subscribe to selected binary markets and detect real ask-side arb."""
    import websockets  # local import: only needed for stream mode
    import certifi

    groups = await _select_binary_groups(MAX_GROUPS)
    if not groups:
        logger.error("No liquid binary markets found for streaming.")
        return {"found": 0, "cumulative_paper_pnl": 0.0, "ticks": 0}

    token_to_group = {}
    all_tokens = []
    for g in groups:
        for t in g["tokens"]:
            token_to_group[t] = g
            all_tokens.append(t)
    best_ask: dict[str, float] = {}
    cumulative = {"pnl": 0.0}
    found = 0
    ticks = 0
    seen_recent: dict[str, float] = {}  # group_id -> last log monotonic time

    logger.info(f"Streaming {len(groups)} binary markets ({len(all_tokens)} tokens) for {duration}s...")
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    start = time.time()
    try:
        async with websockets.connect(WS_URL, ssl=ssl_context) as ws:
            await ws.send(json.dumps({"assets_ids": all_tokens, "type": "market"}))
            logger.info("Subscribed to CLOB orderbook stream.")
            while True:
                if duration and (time.time() - start) >= duration:
                    break
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
                except asyncio.TimeoutError:
                    continue
                data = json.loads(msg)
                events = data if isinstance(data, list) else [data]
                for evt in events:
                    if "asks" not in evt:
                        continue
                    asset_id = evt.get("asset_id", "")
                    ask = best_ask_from_book(evt.get("asks", []))
                    if ask is None or asset_id not in token_to_group:
                        continue
                    best_ask[asset_id] = ask
                    ticks += 1
                    g = token_to_group[asset_id]
                    asks = [best_ask.get(t) for t in g["tokens"]]
                    if any(a is None for a in asks):
                        continue
                    # de-dupe: at most one log per group per 30s
                    now = time.time()
                    if now - seen_recent.get(g["group_id"], 0) < 30:
                        continue
                    opp = build_opportunity(
                        "binary_sum_to_one", g["group_id"], g["question"],
                        g["tokens"], asks, "ws_ask", cumulative,
                    )
                    if opp:
                        seen_recent[g["group_id"]] = now
                        log_opportunity(opp)
                        found += 1
                        logger.info(
                            f"\U0001f911 ARB ask(YES)+ask(NO)={opp['sum_ask']} "
                            f"net={opp['net_edge_pct']*100:.2f}% on {opp['question'][:40]!r}"
                        )
    except Exception as e:  # noqa: BLE001 - network resilience
        logger.error(f"Stream error: {e}")
    return {"found": found, "cumulative_paper_pnl": cumulative["pnl"], "ticks": ticks}


# ===========================================================================
# Entry point
# ===========================================================================

async def run(mode: str, duration: int) -> None:
    logger.info(f"ArbAgent starting | mode={mode} DRY_RUN={DRY_RUN} live_gate={is_live()}")
    if is_live():
        logger.warning("Live gate is OPEN, but agent_arb only paper-detects; no real orders are sent here.")
    if mode == "stream":
        summary = await scan_stream(duration)
    else:
        summary = await scan_snapshot()

    summary.update({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "type": "arb_session_summary",
        "mode": mode,
        "fee_pct": FEE_PCT,
        "gas_usd": GAS_USD,
        "edge_buffer_pct": EDGE_BUFFER_PCT,
    })
    log_opportunity(summary)
    logger.info("=" * 60)
    logger.info(f"ArbAgent done | opportunities={summary.get('found')} "
                f"| paper PnL=${summary.get('cumulative_paper_pnl')}")
    logger.info("=" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(description="Polymarket sum-to-one / NegRisk arbitrage detector (paper)")
    parser.add_argument("--mode", choices=["snapshot", "stream"], default="snapshot",
                        help="snapshot=Gamma one-shot scan; stream=CLOB WebSocket real asks")
    parser.add_argument("--duration", type=int, default=30,
                        help="Stream mode: seconds to run (ignored in snapshot)")
    args = parser.parse_args()
    asyncio.run(run(args.mode, args.duration))


if __name__ == "__main__":
    main()
