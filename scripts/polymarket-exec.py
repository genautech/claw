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


def _load_status_map() -> dict:
    """Load recommendation approval status from dashboard."""
    try:
        path = PROJECT_ROOT / "data" / "recommendation-status.json"
        if path.exists():
            return json.loads(path.read_text())
    except Exception:
        pass
    return {}


def _rec_id(rec: dict) -> str:
    return str(rec.get("id") or rec.get("market_id") or rec.get("timestamp") or "")


def _confidence_rank(level: str) -> int:
    return {"LOW": 1, "MEDIUM": 2, "HIGH": 3}.get(level.upper(), 0)


def _should_execute_rec(rec: dict, status_map: dict, risk_cfg: dict) -> tuple[bool, str]:
    """Return whether a recommendation may be executed and why."""
    rid = _rec_id(rec)
    if not rid:
        return False, "missing id"

    entry = status_map.get(rid, {})
    status = entry.get("status", "pending")
    if status == "rejected":
        return False, "rejected"
    if status == "accepted":
        return True, "accepted"

    if risk_cfg.get("autoExecute"):
        if rec.get("source") != "polywhale_v2":
            return False, "legacy_or_unverified_source"
        min_conf = str(risk_cfg.get("minConfidence", "MEDIUM")).upper()
        min_edge = float(risk_cfg.get("minEdge", 5))
        conf = str(rec.get("confidence", "LOW")).upper()
        edge = float(rec.get("edge", 0) or 0) * 100
        if _confidence_rank(conf) >= _confidence_rank(min_conf) and edge >= min_edge:
            return True, "autoExecute"
        return False, "autoExecute filters not met"

    return False, "pending approval"


def _effective_max_trade_usd(risk_cfg: dict) -> float:
    """Dashboard config is the operational source; env MAX_TRADE_USD is fallback only."""
    if risk_cfg.get("maxTrade") is not None:
        return float(risk_cfg["maxTrade"])
    return MAX_TRADE_USD


def _fetch_usdc_balance() -> float:
    """Sync USDC balance for reserve-floor checks."""
    try:
        wrapper = get_clob_client()
        from py_clob_client.clob_types import BalanceAllowanceParams
        res = wrapper.client.get_balance_allowance(BalanceAllowanceParams(asset_type="COLLATERAL"))
        return float(res.get("balance", "0")) / 10**6
    except Exception as e:
        logger.warning(f"Balance fetch for validation failed: {e}")
        return 0.0

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
CLOB_MIN_PRICE = 0.01
CLOB_MAX_PRICE = 0.99
CLOB_MIN_SHARES = 5


def _clamp_clob_price(price: float) -> float:
    """Normalize price to Polymarket CLOB tick bounds."""
    return max(CLOB_MIN_PRICE, min(CLOB_MAX_PRICE, price))


def _min_usd_for_shares(price: float, shares: int = CLOB_MIN_SHARES) -> float:
    if price <= 0:
        return 0.0
    return round(shares * price, 4)


def _max_order_usd(risk_cfg: dict) -> tuple[float, Optional[str]]:
    """Max USD for one order given maxTrade, reserve floor, and daily exposure."""
    effective_max = _effective_max_trade_usd(risk_cfg)
    reserve = float(risk_cfg.get("reserveFloor", RESERVE_FLOOR_USD))
    max_daily = float(
        risk_cfg.get("maxDailyExposure", risk_cfg.get("maxDaily", MAX_DAILY_EXPOSURE_USD))
    )

    global daily_exposure_usd, daily_exposure_date
    today = datetime.utcnow().strftime("%Y-%m-%d")
    if daily_exposure_date != today:
        daily_exposure_usd = 0.0
        daily_exposure_date = today

    daily_remaining = max(0.0, max_daily - daily_exposure_usd)
    cap = min(effective_max, daily_remaining)

    balance = _fetch_usdc_balance()
    if balance > 0:
        reserve_cap = max(0.0, balance - reserve)
        cap = min(cap, reserve_cap)

    if cap <= 0:
        if balance > 0:
            return 0.0, (
                f"Sem saldo para ordem após reserva ${reserve:.2f} "
                f"(saldo ${balance:.2f})"
            )
        return 0.0, "Limite diário ou maxTrade esgotado"

    return cap, None


def _auto_fit_order_size(
    requested_usd: float,
    current_price: float,
    risk_cfg: dict,
) -> tuple[float, int, Optional[str], Optional[str]]:
    """
    Auto-size order: min shares, maxTrade, reserve floor, daily cap.
    Returns (size_usd, token_amount, resize_note, error).
    """
    import math

    if current_price <= 0:
        return requested_usd, 0, None, f"Invalid current price: {current_price}"

    max_usd, cap_err = _max_order_usd(risk_cfg)
    if cap_err:
        return 0, 0, None, cap_err

    min_usd = _min_usd_for_shares(current_price)
    if max_usd < min_usd:
        balance = _fetch_usdc_balance()
        reserve = float(risk_cfg.get("reserveFloor", RESERVE_FLOOR_USD))
        return 0, 0, None, (
            f"Saldo insuficiente para mínimo {CLOB_MIN_SHARES} shares "
            f"(${min_usd:.2f} @ ${current_price:.2f}) — disponível ${max_usd:.2f} "
            f"(saldo ${balance:.2f}, reserva ${reserve:.2f})"
        )

    fitted = min(float(requested_usd), max_usd)
    if fitted < min_usd:
        fitted = min_usd

    token_amount = max(CLOB_MIN_SHARES, int(math.ceil(fitted / current_price)))
    actual_usd = round(token_amount * current_price, 4)

    if actual_usd > max_usd:
        token_amount = CLOB_MIN_SHARES
        actual_usd = round(token_amount * current_price, 4)
        if actual_usd > max_usd:
            return 0, 0, None, (
                f"Ordem mínima ${actual_usd:.2f} ({CLOB_MIN_SHARES} shares) "
                f"excede disponível ${max_usd:.2f}"
            )

    resize_note = None
    if abs(actual_usd - float(requested_usd)) > 0.01:
        resize_note = (
            f"Tamanho ajustado ${float(requested_usd):.2f} → ${actual_usd:.2f} "
            f"(reserva/maxTrade/mín {CLOB_MIN_SHARES} shares)"
        )
        logger.info(resize_note)

    return actual_usd, token_amount, resize_note, None


def _resolve_size_and_shares(
    size_usd: float,
    current_price: float,
    effective_max: float,
) -> tuple[float, int, Optional[str]]:
    """Legacy wrapper — prefer _auto_fit_order_size with full risk_cfg."""
    risk_cfg = _load_risk_config()
    if risk_cfg.get("maxTrade") is None:
        risk_cfg = {**risk_cfg, "maxTrade": effective_max}
    actual, tokens, _, err = _auto_fit_order_size(size_usd, current_price, risk_cfg)
    return actual, tokens, err


def _arbitrage_execution_prices(best_bid: float, best_ask: float) -> tuple[float, float]:
    """Cross-spread prices aligned with ArbitrageNinja UI (bid+0.001 / ask-0.001)."""
    buy_price = _clamp_clob_price(best_bid + 0.001)
    sell_price = _clamp_clob_price(best_ask - 0.001)
    return buy_price, sell_price


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

    # Optional valid-market cache (populated by CorrectionAgent)
    valid_ids_path = PROJECT_ROOT / "data" / "valid_market_ids.json"
    if valid_ids_path.exists():
        try:
            valid_data = json.loads(valid_ids_path.read_text())
            valid_set = {str(v) for v in valid_data.get("ids", []) if v}
            if valid_set and mid.isdigit() and mid not in valid_set:
                return False, f"Market ID {mid} not in valid market cache"
        except Exception:
            pass
    
    # Check if executor is stopped due to failures
    if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
        return False, f"Executor stopped after {consecutive_failures} consecutive failures"
    
    # Check max trade size (env + dashboard config)
    risk_cfg = _load_risk_config()
    effective_max = _effective_max_trade_usd(risk_cfg)
    if size_usd > effective_max:
        return False, f"Order size ${size_usd} exceeds max ${effective_max}"
    
    # Check market allowlist
    if ALLOWED_MARKETS and market_id not in ALLOWED_MARKETS:
        return False, f"Market {market_id} not in allowlist"
    
    # Check price bounds
    if max_price < CLOB_MIN_PRICE or max_price > CLOB_MAX_PRICE:
        return False, f"Price {max_price} out of bounds [{CLOB_MIN_PRICE}, {CLOB_MAX_PRICE}]"
    
    # Reserve floor + daily exposure (Brimo)
    reserve = float(risk_cfg.get("reserveFloor", RESERVE_FLOOR_USD))
    max_daily = float(risk_cfg.get("maxDailyExposure", risk_cfg.get("maxDaily", MAX_DAILY_EXPOSURE_USD)))
    global daily_exposure_usd, daily_exposure_date
    today = datetime.utcnow().strftime("%Y-%m-%d")
    if daily_exposure_date != today:
        daily_exposure_usd = 0.0
        daily_exposure_date = today
    if daily_exposure_usd + size_usd > max_daily:
        return False, f"Daily exposure ${daily_exposure_usd + size_usd:.2f} would exceed limit ${max_daily}"

    balance = _fetch_usdc_balance()
    if balance > 0 and (balance - size_usd) < reserve:
        return False, (
            f"Would breach reserve floor ${reserve:.2f} "
            f"(balance ${balance:.2f}, order ${size_usd:.2f})"
        )
    
    return True, None


@app.get("/health")
async def health():
    """Health check endpoint."""
    risk_cfg = _load_risk_config()
    return {
        "status": "ok",
        "dry_run": DRY_RUN,
        "max_trade_usd": _effective_max_trade_usd(risk_cfg),
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

        # Get market data (needed for auto-sizing before validation)
        market = await gamma_client.get_market(market_id)
        token_id = market.yes_token_id if outcome_id.upper() == "YES" else market.no_token_id

        if not token_id:
            error = f"No token ID for outcome {outcome_id}"
            log_trade("order_rejected", order_payload, False, error)
            raise HTTPException(status_code=400, detail=error)

        current_price = market.yes_price if outcome_id.upper() == "YES" else market.no_price
        if current_price is None or current_price <= 0:
            error = f"Invalid current price for {outcome_id}: {current_price}"
            log_trade("order_rejected", order_payload, False, error)
            raise HTTPException(status_code=400, detail=error)

        risk_cfg = _load_risk_config()
        size_usd, token_amount, resize_note, size_err = _auto_fit_order_size(
            size_usd, current_price, risk_cfg
        )
        if size_err:
            log_trade("order_rejected", order_payload, False, size_err)
            raise HTTPException(status_code=400, detail=size_err)
        if resize_note:
            order_payload["sizeUsd"] = size_usd
            order_payload["resizeNote"] = resize_note

        # Validate with fitted size
        valid, error = validate_order(market_id, size_usd, max_price)
        if not valid:
            log_trade("order_rejected", order_payload, False, error)
            raise HTTPException(status_code=400, detail=error)

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
        risk_cfg = _load_risk_config()
        effective_max = _effective_max_trade_usd(risk_cfg)
        requested_size = min(float(req.sizeUsd), effective_max)

        buy_price, sell_price = _arbitrage_execution_prices(float(req.bestBid), float(req.bestAsk))
        if buy_price >= sell_price:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Spread inviável após normalização CLOB "
                    f"(buy ${buy_price:.3f}, sell ${sell_price:.3f})"
                ),
            )

        size, token_amount, resize_note, size_err = _auto_fit_order_size(
            requested_size, buy_price, risk_cfg
        )
        if size_err:
            raise HTTPException(status_code=400, detail=size_err)
        if resize_note:
            details["sizeUsd"] = size
            details["resizeNote"] = resize_note
            logger.info(f"Arbitrage {resize_note}")

        valid, error = validate_order(market_id, size, buy_price)
        if not valid:
            raise HTTPException(status_code=400, detail=error)
        
        real_pnl = profit * size
        execution_mode = "simulated" if DRY_RUN else "live"

        live_order_id_buy = None
        live_order_id_sell = None
        exec_error = None

        if not DRY_RUN:
            logger.info("Executando arbitragem real (two-legged) via CLOB...")
            try:
                client = get_clob_client()
                market = await gamma_client.get_market(market_id)
                token_id = market.yes_token_id
                # size/token_amount already fitted above

                logger.info(
                    f"BUY GTC: token {token_id[:8]}... amount {token_amount} @ {buy_price}"
                )
                order_id_buy, error_buy = client.buy_gtc(token_id, token_amount, buy_price)
                if error_buy:
                    raise Exception(f"Buy leg failed: {error_buy}")
                live_order_id_buy = order_id_buy

                logger.info(
                    f"SELL GTC: token {token_id[:8]}... amount {token_amount} @ {sell_price}"
                )
                order_id_sell, error_sell = client.sell_gtc(token_id, token_amount, sell_price)
                if error_sell:
                    logger.warning(f"Sell leg failed, cancelling buy {order_id_buy}: {error_sell}")
                    if order_id_buy:
                        client.cancel_order(order_id_buy)
                    raise Exception(f"Sell leg failed: {error_sell}")
                live_order_id_sell = order_id_sell
            except Exception as e:
                logger.error(f"Erro na execução da arbitragem real: {e}")
                exec_error = str(e)
                real_pnl = 0
        else:
            execution_mode = "dry"

        evt = {
            "timestamp": datetime.utcnow().isoformat(),
            "type": "spread_capture",
            "market": market_id,
            "asset": req.asset,
            "bestBid": req.bestBid,
            "bestAsk": req.bestAsk,
            "spread": req.spread,
            "profit": profit,
            "cumulative_pnl": real_pnl,
            "size": size,
            "agent": "arbitrage_ninja",
            "execution_mode": execution_mode,
        }

        if live_order_id_buy:
            evt["live_order_id"] = live_order_id_buy
            evt["live_order_id_buy"] = live_order_id_buy
        if live_order_id_sell:
            evt["live_order_id_sell"] = live_order_id_sell
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
    """Process recommendations from PolyWhale (only accepted or autoExecute+filters)."""
    rec_file = PROJECT_ROOT / "data" / "recommendations.jsonl"
    if not rec_file.exists():
        return
    
    processed = set()
    processed_file = PROJECT_ROOT / "data" / "recommendations_processed.txt"
    if processed_file.exists():
        processed = set(processed_file.read_text().splitlines())
    
    status_map = _load_status_map()
    risk_cfg = _load_risk_config()
    effective_max = _effective_max_trade_usd(risk_cfg)
    
    new_orders = []
    with open(rec_file, "r") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
                rec_id = _rec_id(rec)
                if rec_id and rec_id not in processed:
                    should_run, reason = _should_execute_rec(rec, status_map, risk_cfg)
                    if not should_run:
                        logger.info(f"Skipping recommendation {rec_id}: {reason}")
                        continue

                    # Convert PolyWhale recommendation to order
                    if rec.get("decision") in ["BUY_YES", "BUY_NO"]:
                        raw_size = rec.get("sizeUsd")
                        if raw_size is None:
                            raw_size = float(rec.get("risk_pct", 0.05)) * DEFAULT_BALANCE_USD
                        size_usd = min(float(raw_size), effective_max)
                        raw_max = float(rec.get("targetPrice", 0.5) or 0.5)
                        max_price = _clamp_clob_price(raw_max)

                        order = {
                            "marketId": rec.get("market_id"),
                            "gammaMarketId": rec.get("gamma_market_id"),
                            "outcomeId": "YES" if "YES" in rec.get("decision", "") else "NO",
                            "side": "buy",
                            "sizeUsd": size_usd,
                            "maxPrice": max_price
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
                risk_cfg = _load_risk_config()

                market = await gamma_client.get_market(lookup_id)
                outcome_id = order_data.get("outcomeId", "YES")
                token_id = market.yes_token_id if outcome_id.upper() == "YES" else market.no_token_id

                if not token_id:
                    logger.warning(f"Recommendation {rec_id} skipped: no token")
                    processed.add(rec_id)
                    continue

                current_price = market.yes_price if outcome_id.upper() == "YES" else market.no_price
                if not current_price or current_price <= 0:
                    logger.warning(f"⚠️ Recommendation {rec_id} skipped: current_price is {current_price}")
                    log_trade("recommendation_skipped", order_data, False, f"price is {current_price}")
                    processed.add(rec_id)
                    continue

                size_usd, token_amount, resize_note, size_err = _auto_fit_order_size(
                    size_usd, current_price, risk_cfg
                )
                if size_err:
                    logger.warning(f"Recommendation {rec_id} rejected: {size_err}")
                    log_trade("recommendation_failed", order_data, False, size_err)
                    processed.add(rec_id)
                    continue
                if resize_note:
                    order_data["sizeUsd"] = size_usd
                    order_data["resizeNote"] = resize_note
                    logger.info(f"Rec {rec_id}: {resize_note}")

                valid, error = validate_order(market_id, size_usd, max_price)
                if not valid:
                    logger.warning(f"Recommendation {rec_id} rejected: {error}")
                    log_trade("recommendation_failed", order_data, False, error)
                    processed.add(rec_id)
                    continue

                if token_id:
                    client = get_clob_client()
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
