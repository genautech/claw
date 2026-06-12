"""Offline unit tests for scripts/llm_router.py (no network).

Run: python3 -m pytest tests/test_llm_router.py -v
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import llm_router  # noqa: E402


def test_route_known_tasks():
    assert llm_router.route("scan")["tier"] == "scan"
    assert llm_router.route("classify")["tier"] == "scan"
    assert llm_router.route("summarize")["tier"] == "parse"
    assert llm_router.route("correlation")["tier"] == "reasoning"
    assert llm_router.route("hedge")["tier"] == "reasoning"
    assert llm_router.route("trade_decision")["tier"] == "decision"


def test_route_is_case_insensitive_and_falls_back():
    assert llm_router.route("DECISION")["tier"] == "decision"
    assert llm_router.route("totally-unknown")["tier"] == "parse"  # fallback
    assert llm_router.route("")["tier"] == "parse"


def test_route_returns_model_and_pricing():
    plan = llm_router.route("scan")
    assert plan["model"] in llm_router.REGISTRY
    assert "input" in plan["pricing"] and "output" in plan["pricing"]


def test_estimate_cost_full_million():
    # deepseek-chat = 0.28 in + 0.42 out per 1M
    cost = llm_router.estimate_cost("deepseek/deepseek-chat", 1_000_000, 1_000_000)
    assert abs(cost - 0.70) < 1e-9


def test_estimate_cost_partial():
    # gemini flash-lite = 0.075 in + 0.30 out
    cost = llm_router.estimate_cost("google/gemini-2.0-flash-lite-001", 500_000, 250_000)
    assert abs(cost - (0.0375 + 0.075)) < 1e-9


def test_estimate_cost_unknown_model_is_zero():
    assert llm_router.estimate_cost("nope/not-a-model", 1000, 1000) == 0.0


def test_approx_tokens():
    assert llm_router.approx_tokens("") == 1
    assert llm_router.approx_tokens("a" * 40) == 10


def test_cost_summary_and_savings(tmp_path):
    p = tmp_path / "llm_costs.jsonl"
    # Two scan calls on the cheap model with 1M in / 1M out each.
    rec = {
        "type": "llm_call", "task": "scan", "tier": "scan",
        "model": "google/gemini-2.0-flash-lite-001",
        "input_tokens": 1_000_000, "output_tokens": 1_000_000,
        "cost_usd": llm_router.estimate_cost("google/gemini-2.0-flash-lite-001", 1_000_000, 1_000_000),
    }
    with open(p, "w") as f:
        f.write(json.dumps(rec) + "\n")
        f.write(json.dumps(rec) + "\n")

    s = llm_router.cost_summary(p)
    assert s["calls"] == 2
    assert s["input_tokens"] == 2_000_000
    # cheap total = 2 * (0.075 + 0.30) = 0.75
    assert abs(s["total_cost_usd"] - 0.75) < 1e-6
    # baseline (sonnet 3/15) for 2M in + 2M out = 6 + 30 = 36
    assert abs(s["baseline_cost_usd"] - 36.0) < 1e-6
    assert s["savings_usd"] > 35
    assert s["savings_pct"] > 97


def test_cost_summary_missing_file():
    s = llm_router.cost_summary(Path("/tmp/does-not-exist-xyz.jsonl"))
    assert s["calls"] == 0
    assert s["total_cost_usd"] == 0.0
