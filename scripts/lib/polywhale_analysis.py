"""Rule-based + optional LLM market analysis for PolyWhale (no random signals)."""

from __future__ import annotations

import json
import os
import re
import ssl
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
SKILL_PATH = PROJECT_ROOT / "skills" / "polywhale" / "SKILL.md"
BOT_ANALYSES = DATA_DIR / "bot_analyses.jsonl"
DASHBOARD_CONFIG = DATA_DIR / "dashboard-config.json"

CRYPTO_ALIASES: dict[str, str] = {
    "bitcoin": "BTC",
    "btc": "BTC",
    "ethereum": "ETH",
    "eth": "ETH",
    "solana": "SOL",
    "sol": "SOL",
    "xrp": "XRP",
    "bnb": "BNB",
}

_binance_cache: dict[str, tuple[float, float]] = {}


def load_config() -> dict[str, Any]:
    if DASHBOARD_CONFIG.exists():
        try:
            return json.loads(DASHBOARD_CONFIG.read_text())
        except json.JSONDecodeError:
            pass
    return {"minEdge": 8, "minConfidence": "MEDIUM"}


def effective_min_edge_pct(config: dict[str, Any]) -> float:
    floor = float(config.get("minEdgeFloor", config.get("minEdge", 8)))
    base = max(floor, float(config.get("minEdge", floor)))
    edges: list[float] = []
    if BOT_ANALYSES.exists():
        lines = [ln for ln in BOT_ANALYSES.read_text().strip().split("\n") if ln.strip()]
        for line in lines[-20:]:
            try:
                row = json.loads(line)
                suggested = (row.get("params") or {}).get("suggested_min_edge")
                if suggested is not None:
                    edges.append(float(suggested))
            except (json.JSONDecodeError, TypeError, ValueError):
                continue
    if edges:
        bot_edge = sum(edges) / len(edges)
        return max(base, bot_edge)
    return base


def parse_yes_price(market: dict[str, Any]) -> float | None:
    prices = market.get("outcomePrices", "[]")
    if isinstance(prices, str):
        try:
            prices = json.loads(prices)
        except json.JSONDecodeError:
            return None
    if not prices:
        return None
    try:
        yes_price = float(prices[0])
    except (TypeError, ValueError):
        return None
    if yes_price <= 0 or yes_price >= 1:
        return None
    return yes_price


def hours_to_resolution(market: dict[str, Any]) -> float | None:
    raw = market.get("endDate") or market.get("endDateIso") or market.get("umaEndDate")
    if not raw:
        return None
    try:
        text = str(raw).replace("Z", "+00:00")
        end = datetime.fromisoformat(text)
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        delta = end - datetime.now(timezone.utc)
        return delta.total_seconds() / 3600
    except (TypeError, ValueError):
        return None


def detect_crypto_symbol(question: str) -> str | None:
    lower = question.lower()
    for alias, symbol in CRYPTO_ALIASES.items():
        if re.search(rf"\b{re.escape(alias)}\b", lower):
            return symbol
    return None


def is_up_down_market(question: str) -> bool:
    lower = question.lower()
    return "up" in lower and "down" in lower or "higher" in lower or "lower" in lower


def fetch_binance_24h_change(symbol: str) -> float | None:
    if symbol in _binance_cache:
        return _binance_cache[symbol][1]
    url = f"https://api.binance.com/api/v3/ticker/24hr?symbol={symbol}USDT"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "PolyWhale/2.0"})
        with urllib.request.urlopen(req, timeout=8, context=SSL_CTX) as resp:
            data = json.loads(resp.read().decode())
        change = float(data.get("priceChangePercent", 0)) / 100.0
        _binance_cache[symbol] = (datetime.now(timezone.utc).timestamp(), change)
        return change
    except Exception:
        return None


def classify_strategy(market: dict[str, Any], question: str) -> str:
    lower = question.lower()
    symbol = detect_crypto_symbol(question)
    if symbol and is_up_down_market(question):
        return "arbitrage"
    hours = hours_to_resolution(market)
    if hours is not None and hours < 72:
        return "mispricing"
    volume = float(market.get("volume24hr", 0) or 0)
    if volume > 75_000:
        return "carry"
    if any(word in lower for word in ("temperature", "weather", "rain", "hurricane")):
        return "weather"
    return "whale_tracking"


def estimate_fair_yes(
    market: dict[str, Any],
    yes_price: float,
    strategy: str,
    question: str,
) -> tuple[float, list[str]]:
    sources = ["gamma_api"]
    fair = yes_price
    symbol = detect_crypto_symbol(question)

    if strategy == "arbitrage" and symbol:
        change = fetch_binance_24h_change(symbol)
        if change is not None:
            sources.append("binance_24h")
            lower = question.lower()
            momentum_bias = max(-0.12, min(0.12, change * 2.5))
            if "up" in lower or "higher" in lower:
                fair = 0.5 + momentum_bias
            elif "down" in lower or "lower" in lower:
                fair = 0.5 - momentum_bias
            else:
                fair = yes_price + momentum_bias * 0.5

    elif strategy == "mispricing":
        hours = hours_to_resolution(market)
        if hours is not None and hours < 48:
            sources.append("resolution_window")
            if yes_price > 0.85:
                fair = min(0.97, yes_price + 0.03)
            elif yes_price < 0.15:
                fair = max(0.03, yes_price - 0.03)

    elif strategy == "carry":
        volume = float(market.get("volume24hr", 0) or 0)
        liquidity = float(market.get("liquidity", 0) or 0)
        if volume > 200_000 and 0.15 < yes_price < 0.85:
            sources.append("volume_liquidity")
            fair = yes_price + (0.5 - yes_price) * 0.08

    return fair, sources


def edge_to_confidence(edge_abs: float, volume: float) -> str:
    if edge_abs >= 0.12 and volume >= 100_000:
        return "HIGH"
    if edge_abs >= 0.08:
        return "MEDIUM"
    return "LOW"


def analyze_market(
    market: dict[str, Any],
    config: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    config = config or load_config()
    min_edge_pct = effective_min_edge_pct(config)
    min_edge = min_edge_pct / 100.0

    yes_price = parse_yes_price(market)
    if yes_price is None:
        return None

    question = str(market.get("question") or market.get("title") or "Unknown")
    volume = float(market.get("volume24hr", 0) or 0)
    if volume < 5_000:
        return None

    strategy = classify_strategy(market, question)
    fair_yes, sources = estimate_fair_yes(market, yes_price, strategy, question)
    edge_signed = fair_yes - yes_price
    edge_abs = abs(edge_signed)

    if edge_abs < min_edge:
        return None

    if edge_signed > 0:
        decision = "BUY_YES"
        target = min(0.99, fair_yes)
    else:
        decision = "BUY_NO"
        target = max(0.01, 1.0 - fair_yes)

    confidence = edge_to_confidence(edge_abs, volume)
    min_conf = str(config.get("minConfidence", "MEDIUM")).upper()
    conf_rank = {"LOW": 1, "MEDIUM": 2, "HIGH": 3}
    if conf_rank.get(confidence, 1) < conf_rank.get(min_conf, 2):
        return None

    market_id = str(market.get("conditionId") or market.get("id") or "unknown")
    ts = datetime.now(timezone.utc)
    rec_id = f"rec_{ts.strftime('%Y%m%d_%H%M%S')}_{market_id[-6:]}"

    reason_parts = [
        f"{strategy}: fair≈{fair_yes:.2%} vs mkt {yes_price:.2%}",
        f"edge {edge_abs:.1%} (min {min_edge_pct:.0f}%)",
    ]
    if "binance_24h" in sources:
        symbol = detect_crypto_symbol(question)
        change = fetch_binance_24h_change(symbol) if symbol else None
        if change is not None:
            reason_parts.append(f"Binance 24h {change:+.1%}")

    return {
        "id": rec_id,
        "timestamp": ts.isoformat(),
        "market_id": market_id,
        "gamma_market_id": str(market.get("id", "")),
        "description": question[:100],
        "decision": decision,
        "targetPrice": round(target, 4),
        "edge": round(edge_abs, 4),
        "confidence": confidence,
        "risk_pct": round(min(edge_abs * 0.4, 0.05), 4),
        "reason": " | ".join(reason_parts),
        "strategy": strategy,
        "data_sources": sources,
        "source": "polywhale_v2",
        "analysis_method": "heuristic",
        "liquidity_usd": float(market.get("liquidity", 0) or 0),
        "volume24hr": volume,
    }


def get_anthropic_key() -> str | None:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        return key
    env_file = Path.home() / ".secrets" / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith("ANTHROPIC_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def llm_refine_recommendation(rec: dict[str, Any], market: dict[str, Any]) -> dict[str, Any]:
    """Optional second pass — downgrade to PASS if LLM disagrees."""
    key = get_anthropic_key()
    if not key:
        return rec

    try:
        import anthropic
    except ImportError:
        return rec

    skill_excerpt = ""
    if SKILL_PATH.exists():
        skill_excerpt = SKILL_PATH.read_text()[:2500]

    prompt = f"""You are PolyWhale. Validate this Polymarket recommendation.
Capital rules: min edge 8%, no revenge trades, prefer liquid markets.

Skill excerpt:
{skill_excerpt}

Market JSON:
{json.dumps({k: market.get(k) for k in ('question', 'volume24hr', 'liquidity', 'endDate', 'outcomePrices')}, indent=2)}

Draft recommendation:
{json.dumps(rec, indent=2)}

Return ONLY JSON with keys: decision (BUY_YES|BUY_NO|PASS), edge (0-1 float), confidence (HIGH|MEDIUM|LOW), reason (max 2 lines).
If edge is not real, return PASS with edge 0."""

    try:
        client = anthropic.Anthropic(api_key=key)
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        text = msg.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        parsed = json.loads(text)
        if parsed.get("decision") == "PASS":
            return {}
        rec["decision"] = parsed.get("decision", rec["decision"])
        rec["edge"] = round(float(parsed.get("edge", rec["edge"])), 4)
        rec["confidence"] = parsed.get("confidence", rec["confidence"])
        rec["reason"] = str(parsed.get("reason", rec["reason"]))[:300]
        rec["analysis_method"] = "llm"
        rec["data_sources"] = list(dict.fromkeys(rec.get("data_sources", []) + ["anthropic"]))
    except Exception as exc:
        rec["llm_note"] = f"llm_skipped: {exc}"

    return rec
