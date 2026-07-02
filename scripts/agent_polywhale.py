#!/usr/bin/env python3
"""PolyWhale Agent — real market analysis (heuristic + optional LLM)."""

import argparse
import json
import ssl
import sys
import urllib.request
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from lib.polywhale_analysis import (  # noqa: E402
    analyze_market,
    effective_min_edge_pct,
    llm_refine_recommendation,
    load_config,
)

SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

DATA_DIR = SCRIPT_DIR.parent / "data"
DATA_DIR.mkdir(exist_ok=True)


def fetch_markets(limit: int = 25) -> list:
    url = (
        "https://gamma-api.polymarket.com/markets"
        f"?active=true&limit={limit}&order=volume24hr&ascending=false"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "PolyWhale/2.0"})
        with urllib.request.urlopen(req, timeout=12, context=SSL_CTX) as resp:
            return json.loads(resp.read().decode())
    except Exception as exc:
        print(f"PolyWhale: API error - {exc}", file=sys.stderr)
        return []


def main() -> None:
    parser = argparse.ArgumentParser(description="PolyWhale market analyzer")
    parser.add_argument("--limit", type=int, default=25, help="Markets to fetch from Gamma")
    parser.add_argument("--max-recs", type=int, default=5, help="Max recommendations per cycle")
    parser.add_argument("--llm", action="store_true", help="Refine top candidates with Claude")
    args = parser.parse_args()

    config = load_config()
    min_edge = effective_min_edge_pct(config)
    markets = fetch_markets(args.limit)
    if not markets:
        print("PolyWhale: No markets available")
        return

    candidates: list[tuple[dict, dict]] = []
    for market in markets:
        rec = analyze_market(market, config)
        if rec:
            candidates.append((rec, market))

    candidates.sort(key=lambda item: float(item[0].get("edge", 0)), reverse=True)
    candidates = candidates[: args.max_recs]

    recs: list[dict] = []
    for rec, market in candidates:
        if args.llm:
            refined = llm_refine_recommendation(rec, market)
            if not refined:
                continue
            rec = refined
        recs.append(rec)

    if not recs:
        print(
            f"PolyWhale: No actionable recommendations "
            f"(minEdge={min_edge:.0f}%, scanned={len(markets)})"
        )
        return

    outfile = DATA_DIR / "recommendations.jsonl"
    with outfile.open("a") as handle:
        for row in recs:
            handle.write(json.dumps(row) + "\n")

    methods = {r.get("analysis_method", "heuristic") for r in recs}
    print(
        f"PolyWhale: {len(recs)} recommendations "
        f"(minEdge={min_edge:.0f}%, methods={','.join(sorted(methods))})"
    )


if __name__ == "__main__":
    main()
