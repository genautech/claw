#!/usr/bin/env python3
"""
Polybot Analyzer — analisa wallet do Polymarket e classifica estratégia de bot.

Uso:
  python3 scripts/agent_polybot_analyzer.py <wallet>
  python3 scripts/agent_polybot_analyzer.py --all
  python3 scripts/agent_polybot_analyzer.py --all --apply-config
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

try:
    import httpx
except ImportError:
    print("Instale httpx: pip install httpx")
    sys.exit(1)

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
MEMORY_DIR = BASE_DIR / "memory"
DATA_DIR.mkdir(exist_ok=True)
MEMORY_DIR.mkdir(exist_ok=True)

DEFAULT_WATCHLIST = DATA_DIR / "bot_watchlist.json"
DASHBOARD_CONFIG = DATA_DIR / "dashboard-config.json"
OUT_FILE = DATA_DIR / "bot_analyses.jsonl"

DATA_API = "https://data-api.polymarket.com"


async def get_activity(wallet: str, limit: int = 100) -> list:
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get(f"{DATA_API}/activity?user={wallet}&limit={limit}")
        response.raise_for_status()
        data = response.json()
        return data if isinstance(data, list) else data.get("data", [])


async def get_positions(wallet: str) -> list:
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get(f"{DATA_API}/positions?user={wallet}")
        response.raise_for_status()
        data = response.json()
        return data if isinstance(data, list) else data.get("data", [])


def detect_simultaneous(trades: list) -> tuple[dict, float]:
    by_ts: dict[str, list] = defaultdict(list)
    for trade in trades:
        by_ts[str(trade.get("timestamp", ""))].append(trade)
    simultaneous = {ts: items for ts, items in by_ts.items() if len(items) > 1}
    bot_ratio = len(simultaneous) / len(by_ts) if by_ts else 0
    return simultaneous, round(bot_ratio, 4)


def detect_multi_asset(trades: list) -> dict:
    same_ts_assets: dict[str, set] = defaultdict(set)
    for trade in trades:
        ts = str(trade.get("timestamp", ""))
        title = trade.get("title", "")
        for asset in ["BTC", "ETH", "SOL", "XRP", "BNB"]:
            if asset in title.upper():
                same_ts_assets[ts].add(asset)
    return {ts: assets for ts, assets in same_ts_assets.items() if len(assets) > 1}


def reconstruct_pairs(trades: list) -> dict:
    by_market: dict[str, dict] = defaultdict(lambda: {"up": [], "down": [], "title": ""})
    for trade in trades:
        if trade.get("side") != "BUY":
            continue
        cid = trade.get("conditionId", "")
        if not cid:
            continue
        side_key = "up" if trade.get("outcomeIndex", 0) == 0 else "down"
        try:
            price = float(trade["price"])
        except (KeyError, ValueError, TypeError):
            continue
        by_market[cid][side_key].append(price)
        if not by_market[cid]["title"]:
            by_market[cid]["title"] = trade.get("title", "")

    pairs = {}
    for cid, sides in by_market.items():
        if sides["up"] and sides["down"]:
            avg_up = sum(sides["up"]) / len(sides["up"])
            avg_down = sum(sides["down"]) / len(sides["down"])
            pair_cost = avg_up + avg_down
            pairs[cid] = {
                "title": sides["title"],
                "avg_up": round(avg_up, 4),
                "avg_down": round(avg_down, 4),
                "pair_cost": round(pair_cost, 4),
                "margin": round(1 - pair_cost, 4),
                "n_up": len(sides["up"]),
                "n_down": len(sides["down"]),
            }
    return pairs


def detect_late_resolution(trades: list) -> int:
    return sum(1 for trade in trades if float(trade.get("price", 0) or 0) > 0.97)


def detect_rotation(trades: list) -> int:
    by_market: dict[str, list] = defaultdict(list)
    for trade in trades:
        cid = trade.get("conditionId", "")
        if cid:
            by_market[cid].append(trade)

    rotation_count = 0
    for mkt_trades in by_market.values():
        sorted_trades = sorted(mkt_trades, key=lambda item: item.get("timestamp", 0))
        for i in range(1, len(sorted_trades)):
            prev, curr = sorted_trades[i - 1], sorted_trades[i]
            ts_diff = abs(float(curr.get("timestamp", 0)) - float(prev.get("timestamp", 0)))
            if ts_diff < 30 and prev.get("outcomeIndex") != curr.get("outcomeIndex"):
                rotation_count += 1
    return rotation_count


def classify_strategy(
    bot_ratio: float,
    multi_asset: dict,
    pairs: dict,
    late_res_count: int,
    rotation_count: int,
    total_trades: int,
) -> str:
    scores: dict[str, int] = {
        "5.3 Inventory Market-Making": 0,
        "5.2 Temporal Arbitrage": 0,
        "5.1 Dynamic Rotation": 0,
        "5.5 Late-Resolution Capture": 0,
        "5.4 Hedged Directional": 0,
    }

    if bot_ratio > 0.10:
        scores["5.3 Inventory Market-Making"] += 3
    if len(multi_asset) > 0:
        scores["5.3 Inventory Market-Making"] += 3

    if pairs:
        margins = [pair["margin"] for pair in pairs.values()]
        avg_margin = sum(margins) / len(margins)
        if avg_margin > 0.10:
            scores["5.2 Temporal Arbitrage"] += 3
        if avg_margin > 0.05:
            scores["5.4 Hedged Directional"] += 1

    if rotation_count > total_trades * 0.1:
        scores["5.1 Dynamic Rotation"] += 3

    if total_trades > 0 and late_res_count / total_trades > 0.20:
        scores["5.5 Late-Resolution Capture"] += 4

    return max(scores, key=lambda key: scores[key])


def estimate_params(pairs: dict) -> dict:
    if not pairs:
        return {}
    margins = [pair["margin"] for pair in pairs.values()]
    avg_margin = sum(margins) / len(margins)
    profitable = sum(1 for margin in margins if margin > 0)
    return {
        "avg_pair_margin": round(avg_margin, 4),
        "profitable_pair_pct": round(profitable / len(margins) * 100, 1),
        "estimated_kelly_fraction": round(max(0.1, min(0.5, avg_margin * 10)), 2),
        "suggested_min_edge": max(5, round(avg_margin * 100 * 0.6)),
    }


def normalize_wallet(wallet: str) -> str:
    if wallet.startswith("0x") and "-" in wallet:
        return wallet.split("-")[0]
    return wallet


def load_watchlist(path: Path | None = None) -> list[str]:
    watchlist_path = path or Path(os.environ.get("POLYBOT_WATCHLIST", DEFAULT_WATCHLIST))
    if not watchlist_path.is_absolute():
        watchlist_path = BASE_DIR / watchlist_path

    if not watchlist_path.exists():
        print(f"Watchlist não encontrada: {watchlist_path}", file=sys.stderr)
        return []

    data = json.loads(watchlist_path.read_text())
    if not data.get("enabled", True):
        print("Watchlist desabilitada (enabled=false)")
        return []

    wallets = data.get("wallets", [])
    return [normalize_wallet(str(wallet)) for wallet in wallets if wallet]


async def analyze_wallet(wallet: str, limit: int = 100) -> dict:
    wallet = normalize_wallet(wallet)
    print(f"Buscando atividade de {wallet}...")
    trades = await get_activity(wallet, limit=limit)
    positions = await get_positions(wallet)

    if not trades:
        return {"error": "Nenhuma atividade encontrada", "wallet": wallet}

    print(f"  {len(trades)} trades encontrados, {len(positions)} posições abertas")

    _, bot_ratio = detect_simultaneous(trades)
    multi_asset = detect_multi_asset(trades)
    pairs = reconstruct_pairs(trades)
    late_res = detect_late_resolution(trades)
    rotations = detect_rotation(trades)
    strategy = classify_strategy(bot_ratio, multi_asset, pairs, late_res, rotations, len(trades))
    params = estimate_params(pairs)

    return {
        "wallet": wallet,
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
        "total_trades": len(trades),
        "open_positions": len(positions),
        "is_bot": bot_ratio > 0.05,
        "bot_ratio": bot_ratio,
        "multi_asset_timestamps": len(multi_asset),
        "pairs_reconstructed": len(pairs),
        "late_resolution_trades": late_res,
        "rotation_count": rotations,
        "strategy": strategy,
        "params": params,
        "top_pairs": sorted(pairs.values(), key=lambda item: item["margin"], reverse=True)[:5],
    }


def print_report(result: dict) -> None:
    print("\n" + "=" * 60)
    print(f"WALLET: {result['wallet']}")
    print("=" * 60)
    if "error" in result:
        print(f"ERRO: {result['error']}")
        return

    print(f"Bot confirmado:    {'SIM' if result['is_bot'] else 'NÃO'} (ratio={result['bot_ratio']:.1%})")
    print(f"Estratégia:        {result['strategy']}")
    print(f"Trades analisados: {result['total_trades']}")
    print(f"Posições abertas:  {result['open_positions']}")
    print(f"Ativos simultâneos detectados: {result['multi_asset_timestamps']} timestamps")
    print(f"Pares Up/Down reconstruídos:   {result['pairs_reconstructed']}")
    print(f"Trades Late-Resolution (>0.97): {result['late_resolution_trades']}")
    print(f"Rotações detectadas:           {result['rotation_count']}")

    params = result.get("params") or {}
    if params:
        print("\nParâmetros estimados:")
        print(f"  Margem média por par:     {params.get('avg_pair_margin', 0):.1%}")
        print(f"  Pares lucrativos:         {params.get('profitable_pair_pct', 0):.1f}%")
        print(f"  Kelly estimado:           {params.get('estimated_kelly_fraction', 0):.2f}")
        print(f"  minEdge sugerido:         {params.get('suggested_min_edge', 5)}%")

    top_pairs = result.get("top_pairs") or []
    if top_pairs:
        print("\nTop pares (por margem):")
        for pair in top_pairs[:3]:
            title = pair.get("title", "")[:50]
            print(f"  {title}")
            print(
                f"    pair_cost={pair['pair_cost']:.3f}  margem={pair['margin']:.3f}  "
                f"({pair['n_up']}Up/{pair['n_down']}Down)"
            )

    print("=" * 60)


def save_result(result: dict) -> None:
    if "error" in result:
        return
    with OUT_FILE.open("a") as handle:
        handle.write(json.dumps(result) + "\n")
    print(f"\nSalvo em {OUT_FILE}")


def append_memory(result: dict) -> None:
    if "error" in result:
        return

    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    memory_file = MEMORY_DIR / f"{day}.md"
    params = result.get("params") or {}
    entry = (
        f"\n[bot-analysis] {result['analyzed_at'][:10]} — Wallet {result['wallet']}\n"
        f"Tipo: {result['strategy']}\n"
        f"Bot ratio: {result['bot_ratio']:.1%}\n"
        f"Trades: {result['total_trades']} | Posições: {result['open_positions']}\n"
        f"Avg pair margin: {params.get('avg_pair_margin', 'n/a')}\n"
        f"Calibração sugerida: minEdge={params.get('suggested_min_edge', 'n/a')}, "
        f"Kelly={params.get('estimated_kelly_fraction', 'n/a')}\n"
    )

    if memory_file.exists():
        existing = memory_file.read_text()
        if result["wallet"] in existing and "[bot-analysis]" in existing:
            return

    with memory_file.open("a") as handle:
        handle.write(entry)
    print(f"Memória atualizada: {memory_file}")


def apply_dashboard_config(results: list[dict]) -> None:
    edges = [
        result["params"]["suggested_min_edge"]
        for result in results
        if result.get("params", {}).get("suggested_min_edge") is not None
    ]
    if not edges:
        print("Nenhum minEdge sugerido para aplicar.")
        return

    suggested = round(sum(edges) / len(edges))
    config = {}
    if DASHBOARD_CONFIG.exists():
        config = json.loads(DASHBOARD_CONFIG.read_text())

    previous = config.get("minEdge")
    floor = max(8, int(config.get("minEdgeFloor", 8)))
    config["minEdge"] = max(floor, suggested)
    DASHBOARD_CONFIG.write_text(json.dumps(config, indent=2) + "\n")
    print(f"dashboard-config.json: minEdge {previous} -> {config['minEdge']} (floor={floor})")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Polybot Analyzer")
    parser.add_argument("wallet", nargs="?", help="Wallet address or slug")
    parser.add_argument("--all", action="store_true", help="Analyze all wallets in watchlist")
    parser.add_argument("--apply-config", action="store_true", help="Apply suggested minEdge to dashboard-config.json")
    parser.add_argument("--limit", type=int, default=int(os.environ.get("POLYBOT_LIMIT", "100")))
    return parser.parse_args()


async def run() -> int:
    args = parse_args()
    wallets: list[str] = []

    if args.all:
        wallets = load_watchlist()
        if not wallets:
            return 1
    elif args.wallet:
        wallets = [args.wallet]
    else:
        print("Uso: python3 scripts/agent_polybot_analyzer.py <wallet> | --all [--apply-config]")
        return 1

    results: list[dict] = []
    for wallet in wallets:
        result = await analyze_wallet(wallet, limit=args.limit)
        print_report(result)
        save_result(result)
        append_memory(result)
        results.append(result)

    if args.apply_config:
        successful = [result for result in results if "error" not in result]
        apply_dashboard_config(successful)

    return 0 if any("error" not in result for result in results) else 1


def main() -> None:
    raise SystemExit(asyncio.run(run()))


if __name__ == "__main__":
    main()
