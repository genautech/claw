#!/usr/bin/env python3
"""PolyClaw Agent - Autonomous paper trading on Polymarket."""

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

def fetch_markets(limit=10):
    url = f"https://gamma-api.polymarket.com/markets?active=true&limit={limit}&order=volume24hr&ascending=false"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "PolyClaw/1.0"})
        with urllib.request.urlopen(req, timeout=10, context=SSL_CTX) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print(f"PolyClaw: API error - {e}", file=sys.stderr)
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

    fair_value = yes_price + random.uniform(-0.15, 0.15)
    fair_value = max(0.05, min(0.95, fair_value))
    edge = abs(fair_value - yes_price)

    if edge < 0.05:
        return None

    decision = "BUY_YES" if fair_value > yes_price else "BUY_NO"
    confidence = "HIGH" if edge > 0.12 else "MEDIUM" if edge > 0.08 else "LOW"

    return {
        "id": f"sim_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{random.randint(100,999)}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "market_id": str(market.get("conditionId", market.get("id", "unknown"))),
        "description": market.get("question", "Unknown")[:100],
        "decision": decision,
        "targetPrice": round(fair_value, 4),
        "currentPrice": round(yes_price, 4),
        "edge": round(edge, 4),
        "confidence": confidence,
        "risk_pct": round(min(edge * 0.5, 0.05), 4),
        "reason": f"Edge detected: fair value {fair_value:.2f} vs market {yes_price:.2f}",
        "exit_rules": {
            "stop_loss": round(yes_price * 0.7, 2),
            "take_profit": round(yes_price * 1.4, 2),
            "time_limit": "7d",
        },
        "status": "SIMULATED",
        "data_sources": ["gamma_api"],
    }

def main():
    markets = fetch_markets()
    if not markets:
        print("PolyClaw: No markets available")
        return

    trades = []
    for m in markets[:5]:
        trade = analyze_market(m)
        if trade:
            trades.append(trade)

    if trades:
        outfile = DATA_DIR / "simulated_trades.jsonl"
        with open(outfile, "a") as f:
            for t in trades:
                f.write(json.dumps(t) + "\n")
        print(f"PolyClaw: {len(trades)} simulated trades logged to {outfile}")
    else:
        print("PolyClaw: No tradeable edges found this cycle")

if __name__ == "__main__":
    main()
