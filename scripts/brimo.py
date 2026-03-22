#!/usr/bin/env python3
"""
Brimo — Sell Specialist Agent
Monitors open positions and executes sell orders based on:
- Take-Profit (TP): auto-sell when position gains >= TP%
- Stop-Loss (SL): auto-sell when position loses >= SL%
- Trailing Stop: tracks peak PnL, sells when price drops TRAILING% from peak
- Reserve Floor: blocks any new buys if balance <= floor

Also processes SELL recommendations from other agents (PolyWhale, PolyClaw).

Usage:
  python scripts/brimo.py --monitor         # Start position monitor loop
  python scripts/brimo.py --check-once      # Single check (for cron)
  python scripts/brimo.py --status          # Print current status
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "references" / "polyclaw-chainstack"))

from lib.gamma_client import GammaClient
from lib.clob_client import ClobClientWrapper

# Setup logging
LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "brimo.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [BRIMO] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_FILE, mode="a"),
    ]
)
logger = logging.getLogger("brimo")

# ─── Configuration ───────────────────────────────────────────────
POLYMARKET_PK = os.environ.get("POLYMARKET_PK", "")
POLYMARKET_ADDRESS = os.environ.get("POLYMARKET_ADDRESS", "")
POLYMARKET_API_KEY = os.environ.get("POLYMARKET_API_KEY", "")
POLYMARKET_API_SECRET = os.environ.get("POLYMARKET_API_SECRET", "")
POLYMARKET_API_PASSPHRASE = os.environ.get("POLYMARKET_API_PASSPHRASE", "")
DRY_RUN = os.environ.get("DRY_RUN", "true").lower() in ("true", "1", "yes")

# Auto-load from OpenClaw config if empty
if not POLYMARKET_PK:
    try:
        with open(os.path.expanduser("~/.openclaw/openclaw.json"), "r") as f:
            cfg = json.load(f)
            env = cfg.get("skills", {}).get("entries", {}).get("polymarket-exec", {}).get("env", {})
            for k, v in env.items():
                if v and not os.environ.get(k):
                    os.environ[k] = str(v)
            POLYMARKET_PK = os.environ.get("POLYMARKET_PK", "")
            POLYMARKET_ADDRESS = os.environ.get("POLYMARKET_ADDRESS", "")
    except Exception:
        pass

# Risk parameters (from env or dashboard config)
RESERVE_FLOOR_USD = float(os.environ.get("RESERVE_FLOOR_USD", "3.0"))
TAKE_PROFIT_PCT = float(os.environ.get("TAKE_PROFIT_PCT", "20.0"))
STOP_LOSS_PCT = float(os.environ.get("STOP_LOSS_PCT", "15.0"))
TRAILING_STOP_PCT = float(os.environ.get("TRAILING_STOP_PCT", "10.0"))
MAX_DAILY_EXPOSURE_USD = float(os.environ.get("MAX_DAILY_EXPOSURE_USD", "20.0"))
MONITOR_INTERVAL = int(os.environ.get("BRIMO_INTERVAL", "60"))  # seconds

# Data files
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)
CONFIG_FILE = DATA_DIR / "dashboard-config.json"
RISK_EVENTS_FILE = DATA_DIR / "risk-events.jsonl"
POSITIONS_FILE = DATA_DIR / "brimo-positions.json"
EXECUTIONS_FILE = DATA_DIR / "executions.jsonl"

# ─── Global State ────────────────────────────────────────────────
peak_prices: dict[str, float] = {}  # token_id -> highest price seen


def load_config() -> dict:
    """Load dashboard config for risk parameters."""
    defaults = {
        "reserveFloor": RESERVE_FLOOR_USD,
        "takeProfit": TAKE_PROFIT_PCT,
        "stopLoss": STOP_LOSS_PCT,
        "trailingStop": TRAILING_STOP_PCT,
        "maxDailyExposure": MAX_DAILY_EXPOSURE_USD,
    }
    try:
        if CONFIG_FILE.exists():
            cfg = json.loads(CONFIG_FILE.read_text())
            return {**defaults, **cfg}
    except Exception:
        pass
    return defaults


def log_risk_event(event_type: str, details: dict, success: bool = True, error: str = None):
    """Log risk event to JSONL file."""
    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "agent": "brimo",
        "event_type": event_type,
        "details": details,
        "success": success,
        "error": error,
    }
    logger.info(f"EVENT: {event_type} | {json.dumps(details, default=str)}")
    try:
        with open(RISK_EVENTS_FILE, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception as e:
        logger.error(f"Failed to write risk event: {e}")


def log_execution(action: str, details: dict, success: bool, error: str = None):
    """Log to shared executions.jsonl."""
    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "action": action,
        "details": {**details, "agent": "brimo"},
        "success": success,
        "error": error,
    }
    try:
        with open(EXECUTIONS_FILE, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception as e:
        logger.error(f"Failed to write execution: {e}")


def load_position_state() -> dict:
    """Load tracked position state (entry prices, peaks, etc)."""
    try:
        if POSITIONS_FILE.exists():
            return json.loads(POSITIONS_FILE.read_text())
    except Exception:
        pass
    return {"positions": {}, "daily_exposure": 0, "daily_date": ""}


def save_position_state(state: dict):
    """Save position state."""
    try:
        POSITIONS_FILE.write_text(json.dumps(state, indent=2, default=str))
    except Exception as e:
        logger.error(f"Failed to save position state: {e}")


def get_clob_client() -> ClobClientWrapper:
    """Initialize CLOB client."""
    if not POLYMARKET_PK or not POLYMARKET_ADDRESS:
        raise ValueError("POLYMARKET_PK and POLYMARKET_ADDRESS must be set")
    return ClobClientWrapper(
        POLYMARKET_PK,
        POLYMARKET_ADDRESS,
        api_key=POLYMARKET_API_KEY or None,
        api_secret=POLYMARKET_API_SECRET or None,
        api_passphrase=POLYMARKET_API_PASSPHRASE or None,
    )


async def get_balance(gamma: GammaClient) -> float:
    """Get current USDC balance."""
    # In real implementation, this queries on-chain balance
    # For now, return from config or env
    try:
        cfg = load_config()
        return float(cfg.get("capitalInitial", 9))
    except Exception:
        return 0.0


async def check_positions(clob: ClobClientWrapper, gamma: GammaClient):
    """
    Core Brimo logic: check all positions against TP/SL/trailing rules.
    """
    config = load_config()
    tp_pct = float(config.get("takeProfit", TAKE_PROFIT_PCT))
    sl_pct = float(config.get("stopLoss", STOP_LOSS_PCT))
    ts_pct = float(config.get("trailingStop", TRAILING_STOP_PCT))
    reserve = float(config.get("reserveFloor", RESERVE_FLOOR_USD))

    state = load_position_state()

    # Reset daily exposure if new day
    today = datetime.utcnow().strftime("%Y-%m-%d")
    if state.get("daily_date") != today:
        state["daily_exposure"] = 0
        state["daily_date"] = today

    # Get open positions via Data API instead of Clob Limit Orders
    try:
        proxy_addr = clob.proxy_address or clob.address
        if not proxy_addr:
            logger.info("📊 No proxy address found")
            return
            
        import httpx
        url = f"https://data-api.polymarket.com/positions?user={proxy_addr}"
        with httpx.Client() as c:
            r = c.get(url, timeout=10.0)
            
        if r.status_code != 200:
            logger.error(f"Failed to fetch Gamma positions: {r.text}")
            return
            
        orders = r.json()
        if not orders:
            logger.info("📊 No open positions found")
            return
    except Exception as e:
        logger.error(f"Failed to fetch positions: {e}")
        log_risk_event("position_fetch_error", {}, False, str(e))
        return

    logger.info(f"📊 Checking {len(orders)} positions | TP: {tp_pct}% | SL: {sl_pct}% | Trailing: {ts_pct}%")

    for order in orders:
        try:
            market_id = order.get("conditionId", "")
            side = order.get("outcome", "buy")
            size = float(order.get("size", 0))
            entry_price = float(order.get("avgPrice", 0))
            
            # The Data API doesn't expose token_id directly, but we can look it up
            # Actually Gamma API gives us asset (which IS the token_id theoretically!)
            # The token_id in CTF is the long integer string, but py-clob-client uses the padded hex!
            # We MUST resolve the token_id from the market info so clob knows what to sell!
            
            market = await gamma.get_market(market_id)
            if market is None:
                continue
            
            # Match outcome name to resolve side and token
            is_yes = (side.lower() == "yes" or side == market.yes_outcome)
            token_id = market.yes_token_id if is_yes else market.no_token_id
            
            if not token_id or entry_price <= 0 or size <= 0:
                continue

            # Track position in state
            pos_key = token_id[:16]
            if pos_key not in state["positions"]:
                state["positions"][pos_key] = {
                    "token_id": token_id,
                    "market_id": market_id,
                    "entry_price": entry_price,
                    "size": size,
                    "peak_price": entry_price,
                    "entered_at": datetime.utcnow().isoformat(),
                }

            tracked = state["positions"][pos_key]

            # Get current market price
            try:
                current_price = market.yes_price if is_yes else market.no_price
                if not current_price or current_price <= 0:
                    continue
            except Exception:
                # If we can't get price, skip this position
                continue

            # Calculate PnL percentage and absolute
            pnl_pct = float(order.get("percentPnl", ((current_price - entry_price) / entry_price) * 100))
            pnl_usd = float(order.get("cashPnl", (current_price - entry_price) * size))

            # Update peak price (for trailing stop)
            if current_price > tracked.get("peak_price", entry_price):
                tracked["peak_price"] = current_price
                state["positions"][pos_key] = tracked

            peak = tracked.get("peak_price", entry_price)
            drop_from_peak = ((peak - current_price) / peak) * 100 if peak > 0 else 0

            # ─── TAKE PROFIT ───
            if pnl_pct >= tp_pct:
                logger.info(f"🎯 TAKE PROFIT triggered on {pos_key} | PnL: {pnl_pct:.1f}% (≥{tp_pct}%)")
                await execute_sell(
                    clob, token_id, size, current_price,
                    reason=f"take_profit_{pnl_pct:.1f}%",
                    market_id=market_id, pnl_usd=pnl_usd
                )
                state["positions"].pop(pos_key, None)
                continue

            # ─── STOP LOSS ───
            if pnl_pct <= -sl_pct:
                logger.info(f"🛑 STOP LOSS triggered on {pos_key} | PnL: {pnl_pct:.1f}% (≤-{sl_pct}%)")
                await execute_sell(
                    clob, token_id, size, current_price,
                    reason=f"stop_loss_{pnl_pct:.1f}%",
                    market_id=market_id, pnl_usd=pnl_usd
                )
                state["positions"].pop(pos_key, None)
                continue

            # ─── TRAILING STOP ───
            if pnl_pct > 0 and drop_from_peak >= ts_pct:
                logger.info(f"📉 TRAILING STOP triggered on {pos_key} | Drop: {drop_from_peak:.1f}% from peak")
                await execute_sell(
                    clob, token_id, size, current_price,
                    reason=f"trailing_stop_{drop_from_peak:.1f}%_from_peak",
                    market_id=market_id, pnl_usd=pnl_usd
                )
                state["positions"].pop(pos_key, None)
                continue

            # Position is fine, log status
            logger.info(f"  ✅ {pos_key} | Entry: ${entry_price:.3f} → ${current_price:.3f} | PnL: {pnl_pct:+.1f}% (${pnl_usd:+.2f})")

        except Exception as e:
            logger.error(f"Error checking position: {e}")

    save_position_state(state)


async def execute_sell(
    clob: ClobClientWrapper,
    token_id: str,
    amount: float,
    current_price: float,
    reason: str,
    market_id: str = "",
    pnl_usd: float = 0,
):
    """Execute a sell order via CLOB."""
    details = {
        "token_id": token_id[:16],
        "market_id": market_id[:20] if market_id else "",
        "amount": amount,
        "price": current_price,
        "reason": reason,
        "pnl_usd": round(pnl_usd, 4),
    }

    if DRY_RUN:
        logger.info(f"  🧪 [DRY-RUN] Would sell {amount:.2f} tokens at ${current_price:.3f} | Reason: {reason}")
        log_risk_event(f"sell_{reason}_dry", details)
        log_execution(f"brimo_sell_dry ({reason})", details, True)
        return

    try:
        order_id, filled, error = clob.sell_fok(token_id, amount, current_price)
        if filled and order_id:
            logger.info(f"  💰 SOLD {amount:.2f} tokens at ~${current_price:.3f} | Order: {order_id} | PnL: ${pnl_usd:+.2f}")
            log_risk_event(f"sell_{reason}", {**details, "order_id": order_id})
            log_execution(f"brimo_sell ({reason})", {**details, "order_id": order_id}, True)
        else:
            logger.error(f"  ❌ Sell failed: {error}")
            log_risk_event(f"sell_{reason}_failed", details, False, error)
            log_execution(f"brimo_sell_failed ({reason})", details, False, error)
    except Exception as e:
        logger.error(f"  ❌ Sell exception: {e}")
        log_risk_event(f"sell_{reason}_error", details, False, str(e))
        log_execution(f"brimo_sell_error ({reason})", details, False, str(e))


async def process_sell_recommendations(gamma: GammaClient, clob: ClobClientWrapper):
    """Process SELL recommendations from other agents."""
    rec_file = DATA_DIR / "recommendations.jsonl"
    if not rec_file.exists():
        return

    processed_file = DATA_DIR / "recommendations_processed.txt"
    processed = set()
    if processed_file.exists():
        processed = set(processed_file.read_text().splitlines())

    with open(rec_file, "r") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
                rec_id = rec.get("id") or rec.get("market_id", "")
                decision = rec.get("decision", "")

                # Only process SELL decisions
                if rec_id in processed or "SELL" not in decision:
                    continue

                market_id = rec.get("market_id", "")
                outcome = "YES" if "YES" in decision else "NO"
                size = float(rec.get("sizeUsd", 1))

                logger.info(f"📋 Processing sell recommendation: {decision} on {market_id[:16]}")

                try:
                    market = await gamma.get_market(market_id)
                    token_id = market.yes_token_id if outcome == "YES" else market.no_token_id
                    price = market.yes_price if outcome == "YES" else market.no_price

                    if token_id and price and price > 0:
                        import math
                        token_amount = math.ceil(size / price)
                        await execute_sell(
                            clob, token_id, token_amount, price,
                            reason=f"recommendation_{decision}",
                            market_id=market_id,
                        )
                except Exception as e:
                    logger.error(f"Failed to process sell rec {rec_id}: {e}")
                    log_execution("brimo_sell_rec_error", {"market_id": market_id}, False, str(e))

                processed.add(rec_id)

            except Exception as e:
                logger.error(f"Failed to parse recommendation: {e}")

    # Save processed
    processed_file.write_text("\n".join(sorted(processed)) + "\n")


async def check_reserve_floor() -> bool:
    """Check if balance is above reserve floor. If not, block buys."""
    config = load_config()
    reserve = float(config.get("reserveFloor", RESERVE_FLOOR_USD))
    balance = float(config.get("capitalInitial", 9))

    if balance <= reserve:
        logger.warning(f"⚠️ RESERVE FLOOR ACTIVE: Balance ${balance:.2f} ≤ Floor ${reserve:.2f}")
        log_risk_event("reserve_floor_active", {"balance": balance, "floor": reserve})
        return False
    return True


def get_status() -> dict:
    """Get Brimo agent status for dashboard."""
    config = load_config()
    state = load_position_state()

    # Read recent risk events
    events = []
    try:
        if RISK_EVENTS_FILE.exists():
            lines = RISK_EVENTS_FILE.read_text().strip().split("\n")
            for line in lines[-20:]:
                try:
                    events.append(json.loads(line))
                except Exception:
                    pass
    except Exception:
        pass

    return {
        "agent": "brimo",
        "status": "active",
        "mode": "DRY_RUN" if DRY_RUN else "LIVE",
        "config": {
            "reserve_floor": float(config.get("reserveFloor", RESERVE_FLOOR_USD)),
            "take_profit_pct": float(config.get("takeProfit", TAKE_PROFIT_PCT)),
            "stop_loss_pct": float(config.get("stopLoss", STOP_LOSS_PCT)),
            "trailing_stop_pct": float(config.get("trailingStop", TRAILING_STOP_PCT)),
            "max_daily_exposure": float(config.get("maxDailyExposure", MAX_DAILY_EXPOSURE_USD)),
        },
        "positions_tracked": len(state.get("positions", {})),
        "daily_exposure": state.get("daily_exposure", 0),
        "recent_events": events[-10:],
        "last_check": datetime.utcnow().isoformat(),
        "interval_seconds": MONITOR_INTERVAL,
    }


async def monitor_loop():
    """Main monitoring loop."""
    logger.info("=" * 60)
    logger.info("🐻 BRIMO — Sell Specialist Agent Starting")
    logger.info(f"   Mode: {'DRY RUN 🧪' if DRY_RUN else 'LIVE 🔴'}")
    logger.info(f"   Take Profit: {TAKE_PROFIT_PCT}%")
    logger.info(f"   Stop Loss: {STOP_LOSS_PCT}%")
    logger.info(f"   Trailing Stop: {TRAILING_STOP_PCT}%")
    logger.info(f"   Reserve Floor: ${RESERVE_FLOOR_USD}")
    logger.info(f"   Check Interval: {MONITOR_INTERVAL}s")
    logger.info("=" * 60)

    gamma = GammaClient(redis_client=None)

    try:
        clob = get_clob_client()
    except Exception as e:
        logger.error(f"❌ Cannot initialize CLOB client: {e}")
        logger.info("Running in monitor-only mode (no sells)")
        clob = None

    log_risk_event("brimo_started", {
        "mode": "dry_run" if DRY_RUN else "live",
        "tp": TAKE_PROFIT_PCT, "sl": STOP_LOSS_PCT, "ts": TRAILING_STOP_PCT,
    })

    cycle = 0
    while True:
        cycle += 1
        logger.info(f"\n{'─' * 40} Cycle {cycle} {'─' * 40}")

        try:
            # 1. Check reserve floor
            floor_ok = await check_reserve_floor()
            if not floor_ok:
                logger.warning("🚨 Balance below reserve floor — monitoring only, buys blocked")

            # 2. Check positions for TP/SL/trailing
            if clob:
                await check_positions(clob, gamma)

            # 3. Process sell recommendations from other agents
            if clob:
                await process_sell_recommendations(gamma, clob)

        except Exception as e:
            logger.error(f"❌ Cycle error: {e}")
            log_risk_event("cycle_error", {"cycle": cycle}, False, str(e))

        logger.info(f"💤 Sleeping {MONITOR_INTERVAL}s until next check...")
        await asyncio.sleep(MONITOR_INTERVAL)


async def single_check():
    """Run a single position check (for cron jobs)."""
    gamma = GammaClient(redis_client=None)
    try:
        clob = get_clob_client()
    except Exception as e:
        logger.error(f"Cannot initialize CLOB: {e}")
        return

    await check_reserve_floor()
    await check_positions(clob, gamma)
    await process_sell_recommendations(gamma, clob)


def main():
    parser = argparse.ArgumentParser(description="🐻 Brimo — Sell Specialist Agent")
    parser.add_argument("--monitor", action="store_true", help="Start continuous position monitor")
    parser.add_argument("--check-once", action="store_true", help="Single position check")
    parser.add_argument("--status", action="store_true", help="Print agent status")
    args = parser.parse_args()

    if args.status:
        status = get_status()
        print(json.dumps(status, indent=2))
    elif args.check_once:
        asyncio.run(single_check())
    elif args.monitor:
        asyncio.run(monitor_loop())
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
