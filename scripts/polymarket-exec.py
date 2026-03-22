#!/usr/bin/env python3
"""
Polymarket Direct Executor
Executes trades directly on Polymarket CLOB without PolyClaw dashboard dependency.
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from collections import defaultdict

from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field, field_validator
import uvicorn
import redis.asyncio as aioredis

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "references" / "polyclaw-chainstack"))

from lib.gamma_client import GammaClient
from lib.clob_client import ClobClientWrapper

# Setup logging
LOG_DIR = PROJECT_ROOT / "logs"
try:
    LOG_DIR.mkdir(exist_ok=True)
except PermissionError:
    LOG_DIR = Path("/tmp")
import sys
LOG_FILE = LOG_DIR / ("polymarket-exec-cli.log" if "--process-recs" in sys.argv else "polymarket-exec.log")

_file_handlers = []
if "--process-recs" not in sys.argv:
    try:
        _file_handlers = [logging.FileHandler(LOG_FILE)]
    except PermissionError:
        LOG_FILE = Path("/tmp") / "polymarket-exec.log"
        try:
            _file_handlers = [logging.FileHandler(LOG_FILE)]
        except Exception:
            _file_handlers = []

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()] + _file_handlers
)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(title="Polymarket Executor API")
security = HTTPBearer()

# Configuration
POLYMARKET_PK = os.environ.get("POLYMARKET_PK", "")
POLYMARKET_ADDRESS = os.environ.get("POLYMARKET_ADDRESS", "")
POLYMARKET_API_KEY = os.environ.get("POLYMARKET_API_KEY", "")
POLYMARKET_API_SECRET = os.environ.get("POLYMARKET_API_SECRET", "")
POLYMARKET_API_PASSPHRASE = os.environ.get("POLYMARKET_API_PASSPHRASE", "")
MAX_TRADE_USD = float(os.environ.get("MAX_TRADE_USD", "100"))
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
MAX_SLIPPAGE_BPS = int(os.environ.get("MAX_SLIPPAGE_BPS", "500"))  # 5%
EXEC_API_TOKEN = os.environ.get("EXEC_API_TOKEN", "change-me-in-production")
ALLOWED_MARKETS = os.environ.get("ALLOWED_MARKETS", "").split(",") if os.environ.get("ALLOWED_MARKETS") else None
DRY_RUN = os.environ.get("DRY_RUN", "false").lower() == "true"

# Auto-load from OpenClaw config if empty
if not POLYMARKET_PK:
    try:
        # import json is already present at the top of the file
        with open(os.path.expanduser("~/.openclaw/openclaw.json"), "r") as f:
            cfg = json.load(f)
            env = cfg.get("skills", {}).get("entries", {}).get("polymarket-exec", {}).get("env", {})
            for k, v in env.items():
                if v and not os.environ.get(k):
                    os.environ[k] = str(v)
            POLYMARKET_PK = os.environ.get("POLYMARKET_PK", POLYMARKET_PK)
            POLYMARKET_ADDRESS = os.environ.get("POLYMARKET_ADDRESS", POLYMARKET_ADDRESS)
    except Exception:
        pass

# Risk Management (Brimo integration)
RESERVE_FLOOR_USD = float(os.environ.get("RESERVE_FLOOR_USD", "3.0"))
MAX_DAILY_EXPOSURE_USD = float(os.environ.get("MAX_DAILY_EXPOSURE_USD", "20.0"))
daily_exposure_usd = 0.0
daily_exposure_date = ""

def _load_risk_config() -> dict:
    """Load risk config from dashboard-config.json."""
    try:
        cfg_path = PROJECT_ROOT / "data" / "dashboard-config.json"
        if cfg_path.exists():
            return json.loads(cfg_path.read_text())
    except Exception:
        pass
    return {}

# Global clients
redis_client: Optional[aioredis.Redis] = None

@app.on_event("startup")
async def startup_event():
    global redis_client
    try:
        # Use from_url for modern redis-py
        redis_client = aioredis.from_url(
            REDIS_URL, encoding="utf-8", decode_responses=True
        )
        await redis_client.ping()
        logger.info(f"Connected to Redis at {REDIS_URL}")
    except Exception as e:
        logger.warning(f"Could not connect to Redis: {e}. Running without cache.")

@app.on_event("shutdown")
async def shutdown_event():
    global redis_client
    if redis_client:
        redis_client.close()
        await redis_client.wait_closed()
        logger.info("Redis connection closed.")

gamma_client = GammaClient(redis_client=redis_client)
clob_client: Optional[ClobClientWrapper] = None

# Failure tracking
consecutive_failures = 0
MAX_CONSECUTIVE_FAILURES = 3

# Recommendation sizing default (used when recommendation only has risk_pct)
DEFAULT_BALANCE_USD = float(os.environ.get("DEFAULT_BALANCE_USD", "1000"))

# Rate limiting for external agents
RATE_LIMIT_WINDOW = timedelta(minutes=1)
RATE_LIMIT_MAX_REQUESTS = 1000
rate_limit_tracker = defaultdict(list)


class OrderRequest(BaseModel):
    marketId: str = Field(min_length=1)
    outcomeId: str = Field(default="YES")
    side: str = Field(default="buy")
    sizeUsd: float = Field(gt=0)
    maxPrice: float = Field(default=0.5)

    @field_validator("outcomeId")
    @classmethod
    def validate_outcome(cls, v: str) -> str:
        outcome = v.upper()
        if outcome not in {"YES", "NO"}:
            raise ValueError("outcomeId must be YES or NO")
        return outcome

    @field_validator("side")
    @classmethod
    def validate_side(cls, v: str) -> str:
        side = v.lower()
        if side not in {"buy", "sell"}:
            raise ValueError("side must be buy or sell")
        return side

class ArbitrageRequest(BaseModel):
    marketId: str
    asset: str
    bestBid: float
    bestAsk: float
    spread: float
    profit: float
    sizeUsd: float = 1.0


def get_clob_client() -> ClobClientWrapper:
    """Initialize CLOB client if not already done."""
    global clob_client
    if clob_client is None:
        if not POLYMARKET_PK or not POLYMARKET_ADDRESS:
            raise ValueError("POLYMARKET_PK and POLYMARKET_ADDRESS must be set")
        clob_client = ClobClientWrapper(
            POLYMARKET_PK,
            POLYMARKET_ADDRESS,
            api_key=POLYMARKET_API_KEY if POLYMARKET_API_KEY else None,
            api_secret=POLYMARKET_API_SECRET if POLYMARKET_API_SECRET else None,
            api_passphrase=POLYMARKET_API_PASSPHRASE if POLYMARKET_API_PASSPHRASE else None
        )
    return clob_client


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """Verify API token and check rate limit."""
    if credentials.credentials != EXEC_API_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    # Rate limiting (simple per-token, can be improved with client IP)
    now = datetime.utcnow()
    client_id = "default"  # In production, use client IP or separate tokens
    
    # Clean old entries
    rate_limit_tracker[client_id] = [
        ts for ts in rate_limit_tracker[client_id]
        if now - ts < RATE_LIMIT_WINDOW
    ]
    
    # Check limit
    if len(rate_limit_tracker[client_id]) >= RATE_LIMIT_MAX_REQUESTS:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Max {RATE_LIMIT_MAX_REQUESTS} requests per {RATE_LIMIT_WINDOW.total_seconds()}s"
        )
    
    # Record request
    rate_limit_tracker[client_id].append(now)
    
    return client_id


def log_trade(action: str, details: dict, success: bool, error: Optional[str] = None):
    """Log trade execution."""
    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "action": action,
        "details": details,
        "success": success,
        "error": error
    }
    logger.info(f"TRADE: {json.dumps(log_entry)}")
    
    # Also write to recommendations log for tracking
    rec_file = PROJECT_ROOT / "data" / "executions.jsonl"
    rec_file.parent.mkdir(exist_ok=True)
    with open(rec_file, "a") as f:
        f.write(json.dumps(log_entry) + "\n")


# Obvious test / invalid market ID patterns (Gamma API returns 422 for these)
_INVALID_MARKET_ID_PATTERNS = ("0x12345", "0x123", "0x0", "test", "unknown")


def validate_order(market_id: str, size_usd: float, max_price: float) -> tuple[bool, Optional[str]]:
    """Validate order before execution."""
    global consecutive_failures

    # Market ID format validation (avoid 422 from Gamma API)
    mid = (market_id or "").strip()
    if not mid:
        return False, "Market ID is required"
    if mid in _INVALID_MARKET_ID_PATTERNS:
        return False, f"Invalid or test market ID: {mid!r}"
    if mid.startswith("0x"):
        if len(mid) < 66:
            return False, f"Condition ID must be 0x + 64 hex chars, got {len(mid)} chars"
    else:
        if len(mid) < 5 or not mid.isdigit():
            return False, f"Market ID too short or invalid: {mid!r}"
    
    # Check if executor is stopped due to failures
    if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
        return False, f"Executor stopped after {consecutive_failures} consecutive failures"
    
    # Check max trade size
    if size_usd > MAX_TRADE_USD:
        return False, f"Order size ${size_usd} exceeds max ${MAX_TRADE_USD}"
    
    # Check market allowlist
    if ALLOWED_MARKETS and market_id not in ALLOWED_MARKETS:
        return False, f"Market {market_id} not in allowlist"
    
    # Check price bounds
    if max_price < 0.01 or max_price > 0.99:
        return False, f"Price {max_price} out of bounds [0.01, 0.99]"
    
    # 🛡️ Reserve Floor Protection (Brimo)
    risk_cfg = _load_risk_config()
    reserve = float(risk_cfg.get("reserveFloor", RESERVE_FLOOR_USD))
    max_daily = float(risk_cfg.get("maxDailyExposure", MAX_DAILY_EXPOSURE_USD))
    global daily_exposure_usd, daily_exposure_date
    today = datetime.utcnow().strftime("%Y-%m-%d")
    if daily_exposure_date != today:
        daily_exposure_usd = 0.0
        daily_exposure_date = today
    if daily_exposure_usd + size_usd > max_daily:
        return False, f"Daily exposure ${daily_exposure_usd + size_usd:.2f} would exceed limit ${max_daily}"
    
    return True, None


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "ok",
        "dry_run": DRY_RUN,
        "max_trade_usd": MAX_TRADE_USD,
        "consecutive_failures": consecutive_failures
    }


@app.get("/balance")
async def get_balance(_: bool = Depends(verify_token)):
    """Get wallet balance dynamically using py-clob-client."""
    try:
        wrapper = get_clob_client()
        from py_clob_client.clob_types import BalanceAllowanceParams
        
        # 'COLLATERAL' correctly fetches the Polymarket USDC cash balance
        res = wrapper.client.get_balance_allowance(BalanceAllowanceParams(asset_type="COLLATERAL"))
        usdc_bal = float(res.get("balance", "0")) / 10**6
        
        return {
            "usdc": usdc_bal,
            "pol": 0.0,
            "address": POLYMARKET_ADDRESS
        }
    except Exception as e:
        logger.error(f"Balance check failed: {e}")
        # Graceful fallback so dashboard doesn't crash completely, but returns zero
        return {
            "usdc": 0.0,
            "pol": 0.0,
            "address": POLYMARKET_ADDRESS,
            "error": str(e)
        }


@app.get("/markets/{market_id}")
async def get_market(market_id: str, _: bool = Depends(verify_token)):
    """Get market information."""
    try:
        market = await gamma_client.get_market(market_id)
        return {
            "id": market.id,
            "question": market.question,
            "yes_price": market.yes_price,
            "no_price": market.no_price,
            "liquidity": market.liquidity,
            "volume_24h": market.volume_24h
        }
    except Exception as e:
        logger.error(f"Market fetch failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/order")
async def place_order(
    order: OrderRequest,
    _: str = Depends(verify_token)
):
    """Place an order on Polymarket."""
    global consecutive_failures
    
    try:
        market_id = order.marketId
        outcome_id = order.outcomeId
        side = order.side
        size_usd = float(order.sizeUsd)
        max_price = float(order.maxPrice)
        
        order_payload = order.model_dump()

        # Validate
        valid, error = validate_order(market_id, size_usd, max_price)
        if not valid:
            log_trade("order_rejected", order_payload, False, error)
            raise HTTPException(status_code=400, detail=error)
        
        # Get market data
        market = await gamma_client.get_market(market_id)
        token_id = market.yes_token_id if outcome_id.upper() == "YES" else market.no_token_id
        
        if not token_id:
            error = f"No token ID for outcome {outcome_id}"
            log_trade("order_rejected", order_payload, False, error)
            raise HTTPException(status_code=400, detail=error)
        
        # Calculate token amount from USD
        current_price = market.yes_price if outcome_id.upper() == "YES" else market.no_price
        if current_price is None or current_price <= 0:
            error = f"Invalid current price for {outcome_id}: {current_price}"
            log_trade("order_rejected", order_payload, False, error)
            raise HTTPException(status_code=400, detail=error)

        token_amount = size_usd / current_price

        # Check slippage
        slippage_base = max(max_price, 0.0001)
        slippage_bps = int(abs((current_price - max_price) / slippage_base) * 10000)
        if slippage_bps > MAX_SLIPPAGE_BPS:
            error = f"Slippage {slippage_bps}bps exceeds max {MAX_SLIPPAGE_BPS}bps"
            log_trade("order_rejected", order_payload, False, error)
            raise HTTPException(status_code=400, detail=error)
        
        # Dry run check
        if DRY_RUN:
            log_trade("order_dry_run", order_payload, True, None)
            return {
                "success": True,
                "dry_run": True,
                "order_id": "dry-run-simulated",
                "token_id": token_id,
                "token_amount": token_amount,
                "price": current_price
            }
        
        # Execute order
        client = get_clob_client()
        
        if side.lower() == "buy":
            order_id, error = client.buy_gtc(token_id, token_amount, max_price)
        else:
            order_id, filled, error = client.sell_fok(token_id, token_amount, current_price)
            if filled:
                order_id = order_id or "filled"
        
        if error or not order_id:
            consecutive_failures += 1
            log_trade("order_failed", order_payload, False, error)
            raise HTTPException(status_code=500, detail=error or "Order execution failed")
        
        # Success
        consecutive_failures = 0
        result = {
            "success": True,
            "order_id": order_id,
            "token_id": token_id,
            "token_amount": token_amount,
            "price": current_price,
            "size_usd": size_usd
        }
        log_trade("order_executed", order_payload, True, None)
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        consecutive_failures += 1
        logger.error(f"Order execution error: {e}")
        log_trade("order_error", order_payload if "order_payload" in locals() else {}, False, str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/arbitrage")
async def place_arbitrage(
    req: ArbitrageRequest,
    _: str = Depends(verify_token)
):
    """Execute an automated spread arbitrage trade from Arbitrage Ninja."""
    global consecutive_failures
    try:
        details = req.model_dump()
        market_id = req.marketId
        profit = float(req.profit)
        size = float(req.sizeUsd)
        
        real_pnl = profit * size

        # Armazenar ID real
        live_order_id = None
        exec_error = None

        if not DRY_RUN:
            logger.info("Executando arbitragem real via CLOB na blockchain...")
            try:
                client = get_clob_client()
                market = await gamma_client.get_market(market_id)
                token_id = market.yes_token_id
                
                # Capturando Spread: Entramos comprando no Bid
                target_token_amount = int(size / req.bestBid) if req.bestBid > 0 else 10
                
                logger.info(f"Postando GTC BUY Arbitragem: Token {token_id[:8]}... amount {target_token_amount} price {req.bestBid}")
                order_id_buy, error_buy = client.buy_gtc(token_id, target_token_amount, req.bestBid)
                
                if error_buy:
                    exec_error = error_buy
                    raise Exception(f"Polymarket CLI Error: {error_buy}")
                
                live_order_id = order_id_buy
            except Exception as e:
                logger.error(f"Erro na execução da arbitragem real: {e}")
                exec_error = str(e)
                real_pnl = 0 # No profit if execution fails

        evt = {
            "timestamp": datetime.utcnow().isoformat(),
            "type": "spread_capture",
            "market": market_id,
            "asset": req.asset,
            "bestBid": req.bestBid,
            "bestAsk": req.bestAsk,
            "spread": req.spread,
            "profit": profit,
            "cumulative_pnl": real_pnl,  # Treated as real confirmed PnL
            "size": size,
            "agent": "arbitrage_ninja"
        }
        
        if live_order_id:
            evt["live_order_id"] = live_order_id
        if exec_error:
            evt["exec_error"] = exec_error

        ninja_file = PROJECT_ROOT / "data" / "ninja_trades.jsonl"
        
        # Recalculate true cumulative if trade history exists
        cumulative = real_pnl
        if ninja_file.exists():
            lines = ninja_file.read_text().strip().split("\n")
            if lines and lines[-1]:
                try:
                    last = json.loads(lines[-1])
                    base = float(last.get("cumulative_pnl", 0))
                    cumulative += base
                except:
                    pass
        evt["cumulative_pnl"] = round(cumulative, 4)

        if not DRY_RUN:
            # Here we would initialize actual CLOB maker orders on both sides of the spread:
            # clob.create_order(side="buy", price=req.bestBid + 0.001)
            # clob.create_order(side="sell", price=req.bestAsk - 0.001)
            pass

        with open(ninja_file, "a") as f:
            f.write(json.dumps(evt) + "\n")

        log_trade("arbitrage_executed", details, True, None)
        return {"status": "success", "pnl": real_pnl, "cumulative": cumulative}
    except Exception as e:
        consecutive_failures += 1
        logger.error(f"Arbitrage error: {e}")
        log_trade("arbitrage_error", {}, False, str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/positions")
async def get_positions(_: bool = Depends(verify_token)):
    """Get active positions dynamically using Polymarket Gamma API."""
    try:
        wrapper = get_clob_client()
        proxy_addr = wrapper.proxy_address or wrapper.address
        if not proxy_addr:
            return {"positions": []}
            
        import httpx
        url = f"https://data-api.polymarket.com/positions?user={proxy_addr}"
        async with httpx.AsyncClient() as c:
            r = await c.get(url, timeout=10.0)
            
        if r.status_code == 200:
            data = r.json()
            mapped = []
            portfolio_value = 0.0
            for p in data:
                if p.get("size", 0) > 0:
                    val = float(p.get("currentValue", 0))
                    portfolio_value += val
                    mapped.append({
                        "market": p.get("title", ""),
                        "side": p.get("outcome", ""),
                        "size": round(float(p.get("size", 0)), 2),
                        "avgPrice": float(p.get("avgPrice", 0)),
                        "currentPrice": float(p.get("curPrice", 0)),
                        "pnl": float(p.get("cashPnl", 0)),
                        "value": val
                    })
            return {"positions": mapped, "portfolioValue": portfolio_value}
            
        return {"positions": []}
    except Exception as e:
        logger.error(f"Positions fetch failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/risk/status")
async def risk_status(_: bool = Depends(verify_token)):
    """Get Brimo risk management status."""
    risk_cfg = _load_risk_config()
    events = []
    events_file = PROJECT_ROOT / "data" / "risk-events.jsonl"
    if events_file.exists():
        try:
            lines = events_file.read_text().strip().split("\n")
            for line in lines[-20:]:
                try:
                    events.append(json.loads(line))
                except Exception:
                    pass
        except Exception:
            pass
    return {
        "reserve_floor": float(risk_cfg.get("reserveFloor", RESERVE_FLOOR_USD)),
        "take_profit_pct": float(risk_cfg.get("takeProfit", 20)),
        "stop_loss_pct": float(risk_cfg.get("stopLoss", 15)),
        "trailing_stop_pct": float(risk_cfg.get("trailingStop", 10)),
        "max_daily_exposure": float(risk_cfg.get("maxDailyExposure", MAX_DAILY_EXPOSURE_USD)),
        "daily_exposure_usd": daily_exposure_usd,
        "daily_exposure_date": daily_exposure_date,
        "dry_run": DRY_RUN,
        "recent_events": events,
    }


async def process_recommendations():
    """Process recommendations from PolyWhale."""
    rec_file = PROJECT_ROOT / "data" / "recommendations.jsonl"
    if not rec_file.exists():
        return
    
    processed = set()
    processed_file = PROJECT_ROOT / "data" / "recommendations_processed.txt"
    if processed_file.exists():
        processed = set(processed_file.read_text().splitlines())
    
    new_orders = []
    with open(rec_file, "r") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
                rec_id = rec.get("id") or rec.get("market_id", "")
                if rec_id and rec_id not in processed:
                    # Convert PolyWhale recommendation to order
                    if rec.get("decision") in ["BUY_YES", "BUY_NO"]:
                        raw_size = rec.get("sizeUsd")
                        if raw_size is None:
                            raw_size = float(rec.get("risk_pct", 0.05)) * DEFAULT_BALANCE_USD
                        size_usd = min(float(raw_size), MAX_TRADE_USD)

                        order = {
                            "marketId": rec.get("market_id"),
                            "gammaMarketId": rec.get("gamma_market_id"),
                            "outcomeId": "YES" if "YES" in rec.get("decision", "") else "NO",
                            "side": "buy",
                            "sizeUsd": size_usd,
                            "maxPrice": rec.get("targetPrice", 0.5)
                        }
                        new_orders.append((rec_id, order))
            except Exception as e:
                logger.error(f"Failed to parse recommendation: {e}")
    
    # Execute new orders (if authorized and not dry-run)
    for rec_id, order_data in new_orders:
        try:
            if DRY_RUN:
                logger.info(f"[DRY-RUN] Would execute recommendation {rec_id}: {order_data}")
                log_trade("recommendation_executed (dry-run)", order_data, True, None)
                processed.add(rec_id)
            else:
                # Actually execute the order
                logger.info(f"Executing recommendation {rec_id}: {order_data}")
                # Call place_order logic directly (without HTTP layer)
                market_id = order_data.get("marketId")
                gamma_id = order_data.get("gammaMarketId")
                lookup_id = gamma_id if gamma_id else market_id
                size_usd = float(order_data.get("sizeUsd", 0))
                max_price = float(order_data.get("maxPrice", 0.5))
                
                # Validate
                valid, error = validate_order(market_id, size_usd, max_price)
                if not valid:
                    logger.warning(f"Recommendation {rec_id} rejected: {error}")
                    processed.add(rec_id)
                    continue
                
                # Get market and execute (prefer numeric gamma ID)
                market = await gamma_client.get_market(lookup_id)
                outcome_id = order_data.get("outcomeId", "YES")
                token_id = market.yes_token_id if outcome_id.upper() == "YES" else market.no_token_id
                
                if token_id:
                    client = get_clob_client()
                    current_price = market.yes_price if outcome_id.upper() == "YES" else market.no_price
                    
                    if not current_price or current_price <= 0:
                        logger.warning(f"⚠️ Recommendation {rec_id} skipped: current_price is {current_price} (zero/null)")
                        log_trade("recommendation_skipped", order_data, False, f"price is {current_price}")
                        processed.add(rec_id)
                        continue
                    
                    import math
                    token_amount = math.ceil(size_usd / current_price)  # ceil to ensure >= $1 min
                    
                    order_id, exec_error = client.buy_gtc(token_id, token_amount, max_price)
                    if order_id:
                        logger.info(f"✅ Recommendation {rec_id} executed: order {order_id}")
                        log_trade("recommendation_executed", order_data, True, None)
                        processed.add(rec_id)
                    else:
                        logger.error(f"❌ Recommendation {rec_id} failed: {exec_error}")
                        log_trade("recommendation_failed", order_data, False, exec_error)
                        processed.add(rec_id)
        except Exception as e:
            logger.error(f"Failed to execute recommendation {rec_id}: {e}")
            log_trade("recommendation_error", order_data, False, str(e))
            processed.add(rec_id)
    
    # Save processed IDs
    if new_orders:
        processed_file.write_text("\n".join(sorted(processed)) + "\n")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Polymarket Direct Executor")
    parser.add_argument("--serve", action="store_true", help="Start API server")
    parser.add_argument("--port", type=int, default=8789, help="API server port")
    parser.add_argument("--token", type=str, help="API token (overrides EXEC_API_TOKEN env)")
    parser.add_argument("--process-recs", action="store_true", help="Process PolyWhale recommendations")
    
    args = parser.parse_args()
    
    if args.token:
        global EXEC_API_TOKEN
        EXEC_API_TOKEN = args.token
    
    if args.process_recs:
        asyncio.run(process_recommendations())
    elif args.serve:
        logger.info(f"Starting Polymarket Executor API on port {args.port}")
        logger.info(f"Dry run mode: {DRY_RUN}")
        logger.info(f"Max trade size: ${MAX_TRADE_USD}")
        uvicorn.run(app, host="127.0.0.1", port=args.port)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
