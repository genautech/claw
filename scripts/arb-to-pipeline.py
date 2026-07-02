#!/usr/bin/env python3
"""Bridge ArbitrageNinja opportunities into PolyWhale recommendation pipeline."""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.absolute()
NINJA_LOG = PROJECT_ROOT / "data" / "ninja_trades.jsonl"
RECOMMENDATIONS = PROJECT_ROOT / "data" / "recommendations.jsonl"
DASHBOARD_CONFIG = PROJECT_ROOT / "data" / "dashboard-config.json"
STATE_FILE = PROJECT_ROOT / "data" / "arb-pipeline-state.json"

PNL_THRESHOLD_USD = 2.0
RELAX_EDGE_DELTA = 1.0


def load_config() -> dict:
    if DASHBOARD_CONFIG.exists():
        try:
            return json.loads(DASHBOARD_CONFIG.read_text())
        except Exception:
            pass
    return {"minEdge": 5}


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {"processedKeys": [], "lastRun": None}


def save_state(state: dict):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))


def read_ninja_trades(limit: int = 50) -> list[dict]:
    if not NINJA_LOG.exists():
        return []
    lines = NINJA_LOG.read_text().strip().split("\n")
    trades = []
    for line in lines[-limit:]:
        if not line.strip():
            continue
        try:
            trades.append(json.loads(line))
        except Exception:
            pass
    return trades


def trade_key(t: dict) -> str:
    return f"{t.get('timestamp', '')}:{t.get('market', t.get('market_id', ''))}:{t.get('spread', '')}"


def main():
    cfg = load_config()
    min_edge = float(cfg.get("minEdge", 5))
    state = load_state()
    processed = set(state.get("processedKeys", []))
    new_recs = 0
    real_pnl_total = 0.0

    for trade in read_ninja_trades():
        spread = float(trade.get("spread", 0) or 0)
        spread_pct = spread * 100 if spread < 1 else spread
        if spread_pct < min_edge:
            continue

        key = trade_key(trade)
        if key in processed:
            continue

        mode = trade.get("execution_mode", "simulated")
        if trade.get("live_order_id") or trade.get("live_order_id_buy"):
            mode = "live"
            real_pnl_total += float(trade.get("profit", 0) or 0) * float(trade.get("size", 1) or 1)

        rec = {
            "id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "market_id": trade.get("market") or trade.get("market_id"),
            "description": f"Arb spread {spread_pct:.2f}% ({mode})",
            "decision": "BUY_YES",
            "confidence": "HIGH",
            "edge": spread if spread < 1 else spread / 100,
            "strategy": "arbitrage_spread",
            "source": "arbitrage_ninja",
            "reason": f"ArbitrageNinja detected spread; execution_mode={mode}",
        }

        with open(RECOMMENDATIONS, "a") as f:
            f.write(json.dumps(rec) + "\n")

        processed.add(key)
        new_recs += 1

    if real_pnl_total >= PNL_THRESHOLD_USD and cfg.get("minEdge", 5) > 3:
        relaxed = max(3, min_edge - RELAX_EDGE_DELTA)
        cfg["minEdge"] = relaxed
        cfg["_arbRelaxedAt"] = datetime.now(timezone.utc).isoformat()
        DASHBOARD_CONFIG.write_text(json.dumps(cfg, indent=2))
        print(f"Relaxed minEdge to {relaxed} (arb PnL ${real_pnl_total:.2f})")

    state["processedKeys"] = list(processed)[-500:]
    state["lastRun"] = datetime.now(timezone.utc).isoformat()
    state["newRecs"] = new_recs
    save_state(state)

    print(json.dumps({"ok": True, "newRecommendations": new_recs, "realPnlWindow": round(real_pnl_total, 4)}))


if __name__ == "__main__":
    main()
