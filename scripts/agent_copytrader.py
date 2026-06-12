#!/usr/bin/env python3
"""
CopyTrader - systematic copy-trading agent (paper-first)
========================================================

Mirrors entries from proven-profitable Polymarket wallets using the public
Data API. The edge is closing the *execution gap* that makes manual following
unprofitable (consistent sizing, dedup, delay, caps) - NOT predicting markets.

Data API (no auth):
  GET /trades?user=<wallet>     recent trades (BUY/SELL, size, price, ...)
  GET /positions?user=<wallet>  positions with cashPnl/realizedPnl (for ranking)
  GET /trades                   global recent feed (wallet discovery)

Modes:
  --mode rank     Rank wallets (watchlist or discovered) by ROI/winrate.
  --mode follow   Detect NEW buy entries from watchlist -> paper copy-trades.
  --mode report   Summarize data/copy_trades.jsonl + go-live gate.

Safety: paper only. Real mirroring is gated behind DRY_RUN=false AND
LIVE_TRADING=true and is intentionally not implemented here.

Output: data/copy_trades.jsonl  +  data/copy_seen.txt (dedup)
"""

import argparse
import asyncio
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx

PROJECT_ROOT = Path(__file__).parent.parent.absolute()
DATA_DIR = PROJECT_ROOT / "data"
COPY_FILE = DATA_DIR / "copy_trades.jsonl"
SEEN_FILE = DATA_DIR / "copy_seen.txt"
WALLETS_FILE = DATA_DIR / "copy_wallets.json"

DATA_API = "https://data-api.polymarket.com"

DRY_RUN = os.environ.get("DRY_RUN", "true").lower() == "true"
LIVE_TRADING = os.environ.get("LIVE_TRADING", "false").lower() == "true"

COPY_MAX_POSITION_USD = float(os.environ.get("COPY_MAX_POSITION_USD", "25"))
COPY_FRACTION = float(os.environ.get("COPY_FRACTION", "0.10"))  # mirror 10% of their notional
COPY_MIN_SIZE_USD = float(os.environ.get("COPY_MIN_SIZE_USD", "5"))
COPY_DELAY_S = int(os.environ.get("COPY_DELAY_S", "120"))       # anti front-run (metadata in paper)
COPY_LOOKBACK = int(os.environ.get("COPY_LOOKBACK", "30"))
COPY_MIN_ROI = float(os.environ.get("COPY_MIN_ROI", "0.0"))     # only follow wallets above this ROI

import logging
logger = logging.getLogger("CopyTrader")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def is_live() -> bool:
    return (not DRY_RUN) and LIVE_TRADING


# ===========================================================================
# Pure functions (no I/O) - unit tested in tests/test_copytrader.py
# ===========================================================================

def trade_usd(trade: dict) -> float:
    """USD notional of a trade = shares * price."""
    try:
        return float(trade.get("size", 0)) * float(trade.get("price", 0))
    except (TypeError, ValueError):
        return 0.0


def trade_id(trade: dict) -> str:
    """Stable id for dedup: prefer tx hash, else wallet+asset+timestamp."""
    h = trade.get("transactionHash")
    if h:
        return str(h)
    return f"{trade.get('proxyWallet','?')}:{trade.get('asset','?')}:{trade.get('timestamp','?')}"


def should_copy(trade: dict, min_size_usd: float = COPY_MIN_SIZE_USD,
                sides: tuple = ("BUY",)) -> bool:
    """Only mirror entries (BUY) above the dust threshold."""
    if str(trade.get("side", "")).upper() not in sides:
        return False
    return trade_usd(trade) >= min_size_usd


def mirror_size(their_usd: float, fraction: float = COPY_FRACTION,
                max_position: float = COPY_MAX_POSITION_USD) -> float:
    """Our paper size = fraction of their notional, capped."""
    if their_usd <= 0:
        return 0.0
    return round(min(max_position, their_usd * fraction), 2)


def score_wallet(positions: list) -> dict:
    """Rank signal from a wallet's positions: ROI, realized PnL, winrate, volume."""
    invested = 0.0
    cash_pnl = 0.0
    realized = 0.0
    wins = 0
    counted = 0
    for p in positions or []:
        try:
            bought = float(p.get("totalBought", p.get("initialValue", 0)) or 0)
            invested += bought
            cash_pnl += float(p.get("cashPnl", 0) or 0)
            realized += float(p.get("realizedPnl", 0) or 0)
            pnl = float(p.get("cashPnl", 0) or 0)
            if bought > 0:
                counted += 1
                if pnl > 0:
                    wins += 1
        except (TypeError, ValueError):
            continue
    roi = (cash_pnl / invested) if invested > 0 else 0.0
    winrate = (wins / counted) if counted > 0 else 0.0
    return {
        "n_positions": len(positions or []),
        "invested_usd": round(invested, 2),
        "cash_pnl_usd": round(cash_pnl, 2),
        "realized_pnl_usd": round(realized, 2),
        "roi": round(roi, 4),
        "winrate": round(winrate, 4),
        # Composite: ROI weighted, with a small volume confidence bump.
        "score": round(roi * (1 + min(counted, 50) / 100.0), 4),
    }


def rank_wallets(wallet_positions: dict) -> list:
    """Return wallets sorted by score desc, each with its metrics."""
    ranked = []
    for wallet, positions in wallet_positions.items():
        metrics = score_wallet(positions)
        ranked.append({"wallet": wallet, **metrics})
    ranked.sort(key=lambda r: r["score"], reverse=True)
    return ranked


# ===========================================================================
# I/O helpers
# ===========================================================================

def _append(path: Path, line: str) -> None:
    try:
        DATA_DIR.mkdir(exist_ok=True)
        with open(path, "a") as f:
            f.write(line + "\n")
    except PermissionError:
        with open(Path("/tmp") / path.name, "a") as f:
            f.write(line + "\n")


def load_seen() -> set:
    if SEEN_FILE.exists():
        return set(SEEN_FILE.read_text().split())
    return set()


def load_watchlist() -> list:
    """Wallets from env COPY_WALLETS (comma-sep) or data/copy_wallets.json."""
    env = os.environ.get("COPY_WALLETS", "").strip()
    if env:
        return [w.strip() for w in env.split(",") if w.strip()]
    if WALLETS_FILE.exists():
        try:
            data = json.loads(WALLETS_FILE.read_text())
            if isinstance(data, list):
                return [str(w) for w in data]
            if isinstance(data, dict):
                return [str(w) for w in data.get("wallets", [])]
        except json.JSONDecodeError:
            pass
    return []


# ===========================================================================
# Network
# ===========================================================================

async def _get(http: httpx.AsyncClient, path: str, params: dict) -> list:
    resp = await http.get(f"{DATA_API}{path}", params=params)
    resp.raise_for_status()
    data = resp.json()
    return data if isinstance(data, list) else []


async def discover_wallets(http: httpx.AsyncClient, limit: int = 100) -> list:
    """Collect distinct wallets from the global recent trade feed."""
    trades = await _get(http, "/trades", {"limit": limit})
    seen = []
    for t in trades:
        w = t.get("proxyWallet")
        if w and w not in seen:
            seen.append(w)
    return seen


async def fetch_positions(http: httpx.AsyncClient, wallet: str, limit: int = 100) -> list:
    return await _get(http, "/positions", {"user": wallet, "limit": limit})


async def fetch_trades(http: httpx.AsyncClient, wallet: str, limit: int) -> list:
    return await _get(http, "/trades", {"user": wallet, "limit": limit})


# ===========================================================================
# Modes
# ===========================================================================

async def run_rank(top: int) -> dict:
    wallets = load_watchlist()
    async with httpx.AsyncClient(timeout=30.0) as http:
        if not wallets:
            logger.info("No watchlist; discovering wallets from global feed...")
            wallets = await discover_wallets(http, limit=120)
        wallets = wallets[:max(top * 3, top)]  # rank a superset, show top
        wallet_positions = {}
        for w in wallets:
            try:
                wallet_positions[w] = await fetch_positions(http, w, limit=100)
            except Exception as e:  # noqa: BLE001
                logger.warning(f"positions failed for {w[:10]}...: {e}")
    ranked = rank_wallets(wallet_positions)
    eligible = [r for r in ranked if r["roi"] >= COPY_MIN_ROI and r["invested_usd"] > 0]
    logger.info(f"Ranked {len(ranked)} wallets; {len(eligible)} eligible (ROI>={COPY_MIN_ROI}).")
    for r in eligible[:top]:
        logger.info(f"  {r['wallet'][:12]}... ROI={r['roi']*100:6.1f}% "
                    f"winrate={r['winrate']*100:4.0f}% PnL=${r['cash_pnl_usd']:>8} "
                    f"n={r['n_positions']}")
    _append(COPY_FILE, json.dumps({
        "type": "wallet_ranking",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ranked": len(ranked), "eligible": len(eligible),
        "top": eligible[:top],
    }))
    return {"ranked": len(ranked), "eligible": len(eligible), "top": eligible[:top]}


async def run_follow(duration: int) -> dict:
    wallets = load_watchlist()
    cumulative = {"pnl": 0.0}
    copied = 0
    seen = load_seen()
    async with httpx.AsyncClient(timeout=30.0) as http:
        if not wallets:
            logger.info("No watchlist; auto-following top-ranked discovered wallets...")
            rank = await run_rank(top=5)
            wallets = [r["wallet"] for r in rank["top"]]
        if not wallets:
            logger.error("No wallets to follow.")
            return {"copied": 0, "cumulative_paper_pnl": 0.0}
        logger.info(f"Following {len(wallets)} wallets (paper, gate_open={is_live()})...")
        if is_live():
            logger.warning("Live gate OPEN, but copytrader only paper-mirrors; no real orders sent.")

        start = time.time()
        while True:
            for w in wallets:
                try:
                    trades = await fetch_trades(http, w, limit=COPY_LOOKBACK)
                except Exception as e:  # noqa: BLE001
                    logger.warning(f"trades failed for {w[:10]}...: {e}")
                    continue
                for t in trades:
                    tid = trade_id(t)
                    if tid in seen or not should_copy(t):
                        continue
                    seen.add(tid)
                    _append(SEEN_FILE, tid)
                    their = trade_usd(t)
                    size = mirror_size(their)
                    if size <= 0:
                        continue
                    # Paper PnL is unknown at entry; we record exposure + a 0 PnL
                    # placeholder (true PnL is realized later by Brimo/position track).
                    rec = {
                        "type": "copy_trade",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "source_wallet": w,
                        "source_name": t.get("name") or t.get("pseudonym") or "?",
                        "side": t.get("side"),
                        "outcome": t.get("outcome"),
                        "conditionId": t.get("conditionId"),
                        "title": str(t.get("title", ""))[:120],
                        "their_price": t.get("price"),
                        "their_size_usd": round(their, 2),
                        "copy_size_usd": size,
                        "copy_fraction": COPY_FRACTION,
                        "delay_s": COPY_DELAY_S,
                        "trade_id": tid,
                        "dry_run": DRY_RUN,
                        "executed": False,
                    }
                    _append(COPY_FILE, json.dumps(rec))
                    copied += 1
                    logger.info(f"\U0001f465 COPY {t.get('side')} ${size} (their ${their:.0f}) "
                                f"@{t.get('price')} '{rec['title'][:40]}' from {w[:10]}...")
            if not duration:
                break
            if (time.time() - start) >= duration:
                break
            await asyncio.sleep(min(15, duration))
    return {"copied": copied, "cumulative_paper_pnl": cumulative["pnl"], "wallets": len(wallets)}


def run_report() -> dict:
    records = []
    if COPY_FILE.exists():
        for line in COPY_FILE.read_text().splitlines():
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    copies = [r for r in records if r.get("type") == "copy_trade"]
    total_size = round(sum(r.get("copy_size_usd", 0) for r in copies), 2)
    wallets = {r.get("source_wallet") for r in copies}
    ready = len(copies) >= int(os.environ.get("GOLIVE_MIN_COPIES", "20"))
    print("=" * 60)
    print("COPY-TRADING REPORT")
    print("=" * 60)
    print(f"  Copy trades (paper):  {len(copies)}")
    print(f"  Distinct sources:     {len(wallets)}")
    print(f"  Total paper notional: ${total_size}")
    print(f"  GO-LIVE GATE:         {'READY' if ready else 'BLOCKED'} "
          f"(need >= {os.environ.get('GOLIVE_MIN_COPIES','20')} copies, have {len(copies)})")
    print("=" * 60)
    return {"copies": len(copies), "sources": len(wallets), "total_size_usd": total_size}


async def _amain(args) -> None:
    if args.mode == "rank":
        await run_rank(args.top)
    elif args.mode == "follow":
        await run_follow(args.duration)


def main() -> None:
    parser = argparse.ArgumentParser(description="Polymarket copy-trading agent (paper-first)")
    parser.add_argument("--mode", choices=["rank", "follow", "report"], default="rank")
    parser.add_argument("--top", type=int, default=10, help="rank: how many to show")
    parser.add_argument("--duration", type=int, default=0, help="follow: seconds to loop (0=one pass)")
    args = parser.parse_args()
    if args.mode == "report":
        run_report()
    else:
        asyncio.run(_amain(args))


if __name__ == "__main__":
    main()
