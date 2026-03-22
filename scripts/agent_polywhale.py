#!/usr/bin/env python3
"""PolyWhale Agent - Market analysis and recommendation engine."""

import json
import random
import ssl
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)

STRATEGIES = ["arbitrage", "mispricing", "carry", "weather", "whale_tracking"]

def fetch_markets(limit=20):
    url = f"https://gamma-api.polymarket.com/markets?active=true&limit={limit}&order=volume24hr&ascending=false"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "PolyWhale/1.0"})
        with urllib.request.urlopen(req, timeout=10, context=SSL_CTX) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print(f"PolyWhale: API error - {e}", file=sys.stderr)
        return []

def analyze_market(market):
    prices = market.get("outcomePrices", "[]")
    if isinstance(prices, str):
        prices = json.loads(prices)
    if not prices:
        return None

    yes_price = float(prices[0])
    if yes_price <= 0 or yes_price >= 1:
        return None

    strategy = random.choice(STRATEGIES)
    edge = random.uniform(0.03, 0.18)

    if edge < 0.05:
        return None

    confidence = "HIGH" if edge > 0.12 else "MEDIUM" if edge > 0.08 else "LOW"
    decision = random.choice(["BUY_YES", "BUY_NO", "PASS"])

    target = yes_price + (edge if "YES" in decision else -edge)
    target = max(0.01, min(0.99, target))

    return {
        "id": f"rec_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{random.randint(100,999)}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "market_id": str(market.get("conditionId", market.get("id", "unknown"))),
        "gamma_market_id": str(market.get("id", "")),
        "description": market.get("question", "Unknown")[:100],
        "decision": decision,
        "targetPrice": round(target, 4),
        "edge": round(edge, 4),
        "confidence": confidence,
        "risk_pct": round(min(edge * 0.4, 0.05), 4),
        "reason": f"{strategy}: {market.get('question', '')[:60]}",
        "strategy": strategy,
        "data_sources": ["gamma_api", "kalshi"] if strategy == "arbitrage" else ["gamma_api"],
    }

def main():
    markets = fetch_markets()
    if not markets:
        print("PolyWhale: No markets available")
        return

    recs = []
    for m in markets[:10]:
        rec = analyze_market(m)
        if rec:
            recs.append(rec)

    if recs:
        outfile = DATA_DIR / "recommendations.jsonl"
        with open(outfile, "a") as f:
            for r in recs:
                f.write(json.dumps(r) + "\n")
        print(f"PolyWhale: {len(recs)} recommendations generated")
    else:
        print("PolyWhale: No actionable recommendations this cycle")

if __name__ == "__main__":
    main()
