#!/usr/bin/env python3
"""
LLMRouter - task-based, multi-provider LLM routing with cost logging.
====================================================================

Replaces the single-model OpenRouter client (only used by hedge.py) with a
router that sends each task to the cheapest adequate model and logs the cost of
every call, so 24/7 scanning stays cheap and premium models are reserved for
hard reasoning.

Tiers (defaults, all reachable through one OpenRouter key; override via env):
  scan      -> ultra-cheap bulk classification/filtering   (Gemini Flash-Lite)
  parse     -> summaries / field extraction                (DeepSeek V3.2)
  reasoning -> correlation / logical implication           (DeepSeek R1)
  decision  -> ambiguous structured decisions              (Claude Haiku)

Pricing is USD per 1M tokens (approx, mid-2026). Update REGISTRY as needed.

CLI:
  python3 scripts/llm_router.py --report           # cost summary + savings
  python3 scripts/llm_router.py --demo "hello"     # live call (needs key)
"""

import argparse
import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx

PROJECT_ROOT = Path(__file__).parent.parent.absolute()
DATA_DIR = PROJECT_ROOT / "data"
COST_FILE = DATA_DIR / "llm_costs.jsonl"

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
LLM_TIMEOUT = 60.0
LLM_MAX_RETRIES = 3

# Model registry: model_id -> price per 1M tokens (input/output). Env-overridable
# per tier so the slugs can be swapped without code changes.
REGISTRY: dict[str, dict] = {
    "google/gemini-2.0-flash-lite-001": {"input": 0.075, "output": 0.30},
    "deepseek/deepseek-chat":           {"input": 0.28,  "output": 0.42},
    "deepseek/deepseek-r1":             {"input": 0.55,  "output": 2.19},
    "anthropic/claude-3.5-haiku":       {"input": 0.80,  "output": 4.00},
    # Premium baseline used only to estimate savings vs naive "use one big model".
    "anthropic/claude-sonnet-4":        {"input": 3.00,  "output": 15.00},
}

# Default model per tier (override with LLM_MODEL_<TIER> env vars).
TIER_DEFAULTS = {
    "scan":      os.environ.get("LLM_MODEL_SCAN", "google/gemini-2.0-flash-lite-001"),
    "parse":     os.environ.get("LLM_MODEL_PARSE", "deepseek/deepseek-chat"),
    "reasoning": os.environ.get("LLM_MODEL_REASONING", "deepseek/deepseek-r1"),
    "decision":  os.environ.get("LLM_MODEL_DECISION", "anthropic/claude-3.5-haiku"),
}

# Task -> tier mapping. Unknown tasks fall back to "parse".
TASK_TIERS = {
    "scan": "scan", "classify": "scan", "filter": "scan",
    "parse": "parse", "summarize": "parse", "extract": "parse",
    "reasoning": "reasoning", "correlation": "reasoning", "implication": "reasoning", "hedge": "reasoning",
    "decision": "decision", "trade_decision": "decision",
}

# Baseline used for savings estimate (a naive single premium model).
BASELINE_MODEL = os.environ.get("LLM_BASELINE_MODEL", "anthropic/claude-sonnet-4")


# ===========================================================================
# Pure functions (no I/O) - unit tested in tests/test_llm_router.py
# ===========================================================================

def route(task: str) -> dict:
    """Resolve a task to its tier + model_id + pricing spec."""
    tier = TASK_TIERS.get((task or "").lower().strip(), "parse")
    model_id = TIER_DEFAULTS[tier]
    spec = REGISTRY.get(model_id, {"input": 0.0, "output": 0.0})
    return {"task": task, "tier": tier, "model": model_id, "pricing": spec}


def estimate_cost(model_id: str, input_tokens: int, output_tokens: int) -> float:
    """USD cost for a call given token counts and the registry pricing."""
    spec = REGISTRY.get(model_id)
    if not spec:
        return 0.0
    cost = (input_tokens / 1_000_000.0) * spec["input"] + \
           (output_tokens / 1_000_000.0) * spec["output"]
    return round(cost, 8)


def approx_tokens(text: str) -> int:
    """Rough token estimate (~4 chars/token) when the API omits usage."""
    return max(1, len(text or "") // 4)


# ===========================================================================
# Cost logging + reporting
# ===========================================================================

def log_cost(record: dict) -> None:
    try:
        DATA_DIR.mkdir(exist_ok=True)
        with open(COST_FILE, "a") as f:
            f.write(json.dumps(record) + "\n")
    except PermissionError:
        with open(Path("/tmp/llm_costs.jsonl"), "a") as f:
            f.write(json.dumps(record) + "\n")


def cost_summary(path: Path = COST_FILE) -> dict:
    """Aggregate logged costs and estimate savings vs the premium baseline."""
    if not path.exists():
        return {"calls": 0, "input_tokens": 0, "output_tokens": 0,
                "total_cost_usd": 0.0, "by_tier": {}, "by_model": {},
                "baseline_model": BASELINE_MODEL, "baseline_cost_usd": 0.0,
                "savings_usd": 0.0, "savings_pct": 0.0}
    calls = 0
    total = 0.0
    in_tok = 0
    out_tok = 0
    by_tier: dict[str, float] = {}
    by_model: dict[str, float] = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if r.get("type") != "llm_call":
            continue
        calls += 1
        c = float(r.get("cost_usd", 0.0))
        total += c
        in_tok += int(r.get("input_tokens", 0))
        out_tok += int(r.get("output_tokens", 0))
        by_tier[r.get("tier", "?")] = round(by_tier.get(r.get("tier", "?"), 0.0) + c, 8)
        by_model[r.get("model", "?")] = round(by_model.get(r.get("model", "?"), 0.0) + c, 8)

    baseline = estimate_cost(BASELINE_MODEL, in_tok, out_tok)
    savings = round(baseline - total, 8)
    savings_pct = round((savings / baseline) * 100, 2) if baseline > 0 else 0.0
    return {
        "calls": calls,
        "input_tokens": in_tok,
        "output_tokens": out_tok,
        "total_cost_usd": round(total, 8),
        "by_tier": by_tier,
        "by_model": by_model,
        "baseline_model": BASELINE_MODEL,
        "baseline_cost_usd": baseline,
        "savings_usd": savings,
        "savings_pct": savings_pct,
    }


# ===========================================================================
# Router (network)
# ===========================================================================

class LLMRouter:
    """Routes a task to a model, calls OpenRouter, logs cost, returns result."""

    def __init__(self, api_key: Optional[str] = None, timeout: float = LLM_TIMEOUT):
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        self.timeout = timeout

    async def complete(
        self,
        messages: list[dict],
        task: str = "parse",
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
    ) -> dict:
        if not self.api_key:
            raise ValueError(
                "OPENROUTER_API_KEY not set. Add it as a secret to enable live LLM calls "
                "(get one at https://openrouter.ai/keys)."
            )
        plan = route(task)
        model_id = plan["model"]
        payload = {"model": model_id, "messages": messages, "temperature": temperature}
        if max_tokens:
            payload["max_tokens"] = max_tokens

        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        async with httpx.AsyncClient(timeout=self.timeout, headers=headers) as client:
            data = await self._post_with_retries(client, payload)

        choice = (data.get("choices") or [{}])[0].get("message", {})
        # DeepSeek R1 sometimes returns empty content with the answer in reasoning_content.
        text = choice.get("content") or choice.get("reasoning_content") or ""

        usage = data.get("usage") or {}
        input_tokens = int(usage.get("prompt_tokens") or approx_tokens(
            "".join(m.get("content", "") for m in messages)))
        output_tokens = int(usage.get("completion_tokens") or approx_tokens(text))
        cost = estimate_cost(model_id, input_tokens, output_tokens)

        record = {
            "type": "llm_call",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "task": task,
            "tier": plan["tier"],
            "model": model_id,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": cost,
        }
        log_cost(record)
        return {"text": text, **record}

    async def _post_with_retries(self, client: httpx.AsyncClient, payload: dict) -> dict:
        for attempt in range(LLM_MAX_RETRIES):
            try:
                resp = await client.post(f"{OPENROUTER_BASE_URL}/chat/completions", json=payload)
                resp.raise_for_status()
                return resp.json()
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429 and attempt < LLM_MAX_RETRIES - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                raise
            except httpx.RequestError:
                if attempt < LLM_MAX_RETRIES - 1:
                    await asyncio.sleep(1)
                    continue
                raise
        raise RuntimeError(f"OpenRouter call failed after {LLM_MAX_RETRIES} attempts")

    def complete_sync(self, messages: list[dict], task: str = "parse", **kwargs) -> dict:
        return asyncio.run(self.complete(messages, task=task, **kwargs))


# ===========================================================================
# CLI
# ===========================================================================

def _print_report() -> None:
    s = cost_summary()
    print("=" * 60)
    print("LLM COST REPORT")
    print("=" * 60)
    print(f"  Calls:            {s['calls']}")
    print(f"  Tokens (in/out):  {s.get('input_tokens', 0)} / {s.get('output_tokens', 0)}")
    print(f"  Total cost:       ${s['total_cost_usd']:.6f}")
    print(f"  By tier:          {s['by_tier']}")
    print(f"  By model:         {s['by_model']}")
    print(f"  Baseline ({s.get('baseline_model','?')}): ${s['baseline_cost_usd']:.6f}")
    print(f"  Savings:          ${s['savings_usd']:.6f} ({s['savings_pct']}%)")
    print("=" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(description="Task-based LLM router + cost report")
    parser.add_argument("--report", action="store_true", help="Print cost summary")
    parser.add_argument("--demo", type=str, help="Send a one-off prompt (live; needs OPENROUTER_API_KEY)")
    parser.add_argument("--task", type=str, default="scan", help="Task type for --demo")
    args = parser.parse_args()

    if args.demo:
        router = LLMRouter()
        plan = route(args.task)
        print(f"Routing task={args.task!r} -> tier={plan['tier']} model={plan['model']}")
        try:
            result = router.complete_sync([{"role": "user", "content": args.demo}], task=args.task)
        except ValueError as e:
            print(f"[skipped] {e}")
            return
        print(f"Response: {result['text'][:500]}")
        print(f"Cost: ${result['cost_usd']:.6f} ({result['input_tokens']}+{result['output_tokens']} tok)")
    else:
        _print_report()


if __name__ == "__main__":
    main()
