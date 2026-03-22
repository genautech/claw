#!/usr/bin/env python3
import asyncio
import websockets
import json
import os
import argparse
import logging
from datetime import datetime, timezone
import sys
import time

# Configure path so we can import clawd libraries
from pathlib import Path
PROJECT_ROOT = Path(__file__).parent.parent.absolute()
POLYCLAW_ROOT = PROJECT_ROOT / "references" / "polyclaw-chainstack"
sys.path.insert(0, str(POLYCLAW_ROOT))
sys.path.insert(0, str(PROJECT_ROOT))

from lib.gamma_client import GammaClient
import redis.asyncio as aioredis

logger = logging.getLogger("ArbitrageNinja")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

DRY_RUN = os.environ.get("DRY_RUN", "true").lower() == "true"
MIN_SPREAD = float(os.environ.get("MIN_SPREAD", "0.02"))  # 2 cents default
WS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
DATA_DIR = PROJECT_ROOT / "data"
NINJA_LOG = DATA_DIR / "ninja_trades.jsonl"

# Performance counters
stats = {
    "ticks": 0,
    "opportunities": 0,
    "simulated_trades": 0,
    "simulated_pnl": 0.0,
    "max_spread": 0.0,
    "avg_spread": 0.0,
    "spreads": [],
}

def log_ninja_trade(trade_data):
    """Append a ninja trade to the JSONL file."""
    try:
        DATA_DIR.mkdir(exist_ok=True)
        with open(NINJA_LOG, "a") as f:
            f.write(json.dumps(trade_data) + "\n")
    except PermissionError:
        with open(Path("/tmp/ninja_trades.jsonl"), "a") as f:
            f.write(json.dumps(trade_data) + "\n")

async def ninja_bot(market_id: str, duration: int = 0):
    logger.info(f"🥷 Starting ArbitrageNinja in DRY_RUN={DRY_RUN}")
    logger.info(f"🎯 Target Market: {market_id}")
    if duration:
        logger.info(f"⏱️  Running for {duration} seconds (quick-sim mode)")
    
    redis_client = aioredis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/0"))
    gamma = GammaClient(redis_client=redis_client)
    
    if market_id.lower() == "auto":
        logger.info("Fetching trending markets to find a liquid target...")
        trending = await gamma.get_trending_markets(limit=5)
        if not trending:
            logger.error("No trending markets found!")
            return
        market = trending[0]
        logger.info(f"Auto-selected trending market: {market.question}")
    else:
        logger.info("Fetching market token IDs from Gamma API...")
        market = await gamma.get_market(market_id)
        
    if not market:
        logger.error("Market not found!")
        return
        
    assets = [market.yes_token_id, market.no_token_id]
    assets = [a for a in assets if a]
    
    logger.info(f"✅ Market found: {market.question}")
    logger.info(f"   YES Token: {market.yes_token_id}")
    logger.info(f"   NO Token:  {market.no_token_id}")
    logger.info(f"   YES Price: ${market.yes_price:.4f} | NO Price: ${market.no_price:.4f}")
    
    logger.info(f"Connecting to Polymarket CLOB WebSocket...")
    
    import ssl, certifi
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    
    start_time = time.time()
    market_question = market.question
    
    try:
        async with websockets.connect(WS_URL, ssl=ssl_context) as ws:
            sub_msg = {"assets_ids": assets, "type": "market"}
            await ws.send(json.dumps(sub_msg))
            logger.info("✅ Successfully subscribed to real-time Orderbook stream!")
            
            while True:
                # Check duration limit
                if duration and (time.time() - start_time) >= duration:
                    logger.info(f"⏱️  Duration limit ({duration}s) reached. Stopping.")
                    break
                
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
                except asyncio.TimeoutError:
                    if duration and (time.time() - start_time) >= duration:
                        break
                    continue
                    
                data = json.loads(msg)
                
                if isinstance(data, list):
                    for evt in data:
                        process_event(evt, market_question)
                else:
                    process_event(data, market_question)
                    
    except websockets.exceptions.ConnectionClosed:
        logger.error("WebSocket connection closed by server!")
    except Exception as e:
        logger.error(f"Stream error: {e}")
    finally:
        # Print final report
        elapsed = time.time() - start_time
        logger.info("━" * 50)
        logger.info("🥷 RELATÓRIO FINAL DO NINJA")
        logger.info("━" * 50)
        logger.info(f"   Mercado: {market_question}")
        logger.info(f"   Duração: {elapsed:.1f}s")
        logger.info(f"   Ticks recebidos: {stats['ticks']}")
        logger.info(f"   Oportunidades (spread > {MIN_SPREAD}): {stats['opportunities']}")
        logger.info(f"   Trades simulados: {stats['simulated_trades']}")
        logger.info(f"   PnL simulado: ${stats['simulated_pnl']:.4f}")
        avg_s = sum(stats['spreads'][-100:]) / max(len(stats['spreads'][-100:]), 1)
        logger.info(f"   Spread médio: ${avg_s:.4f}")
        logger.info(f"   Maior spread: ${stats['max_spread']:.4f}")
        logger.info("━" * 50)
        
        # Save summary
        summary = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": "session_summary",
            "market": market_question,
            "duration_s": round(elapsed, 1),
            "ticks": stats["ticks"],
            "opportunities": stats["opportunities"],
            "simulated_trades": stats["simulated_trades"],
            "simulated_pnl": round(stats["simulated_pnl"], 4),
            "avg_spread": round(avg_s, 4),
            "max_spread": round(stats["max_spread"], 4),
        }
        log_ninja_trade(summary)

def process_event(data, market_question=""):
    if "bids" in data and "asks" in data:
        bids = data["bids"]
        asks = data["asks"]
        if bids and asks:
            try:
                best_bid = float(bids[0]["price"])
                best_ask = float(asks[0]["price"])
                spread = best_ask - best_bid
                asset_id = data.get("asset_id", "")
                
                stats["ticks"] += 1
                stats["spreads"].append(spread)
                if spread > stats["max_spread"]:
                    stats["max_spread"] = spread
                
                # Log every 50 ticks for visibility
                if stats["ticks"] % 50 == 0:
                    avg = sum(stats["spreads"][-50:]) / 50
                    logger.info(f"📊 Tick #{stats['ticks']} | Spread: ${spread:.4f} | Avg(50): ${avg:.4f} | Opps: {stats['opportunities']}")
                
                if spread > MIN_SPREAD:
                    stats["opportunities"] += 1
                    buy_price = best_bid + 0.001
                    sell_price = best_ask - 0.001
                    profit = sell_price - buy_price
                    size_usd = 1.0  # Simulated $1 trade
                    
                    stats["simulated_trades"] += 1
                    stats["simulated_pnl"] += profit * size_usd
                    
                    logger.info(f"🤑 SPREAD #{stats['opportunities']}: ${spread:.4f} on {asset_id[:12]}... | BUY@{buy_price:.3f} SELL@{sell_price:.3f} | Profit: ${profit:.4f}")
                    
                    trade = {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "type": "spread_capture",
                        "market": market_question,
                        "asset_id": asset_id[:20],
                        "best_bid": best_bid,
                        "best_ask": best_ask,
                        "spread": round(spread, 4),
                        "buy_price": round(buy_price, 4),
                        "sell_price": round(sell_price, 4),
                        "profit": round(profit, 4),
                        "size_usd": size_usd,
                        "cumulative_pnl": round(stats["simulated_pnl"], 4),
                        "dry_run": DRY_RUN,
                        "tick": stats["ticks"],
                    }
                    log_ninja_trade(trade)
                    
            except (ValueError, IndexError):
                pass

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="High-Frequency Arbitrage Ninja Agent")
    parser.add_argument("--market", type=str, required=True, help="Market ID to arbitrage on")
    parser.add_argument("--duration", type=int, default=0, help="Run for N seconds then stop (0=forever)")
    args = parser.parse_args()
    
    asyncio.run(ninja_bot(args.market, args.duration))

