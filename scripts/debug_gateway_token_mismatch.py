#!/usr/bin/env python3
"""
Debug script for "gateway token mismatch".
Writes NDJSON to .cursor/debug-3c1436.log (no secrets, only lengths and prefixes).
"""
import json
import os
from pathlib import Path

LOG_PATH = Path(__file__).resolve().parent.parent / ".cursor" / "debug-3c1436.log"
OPENCLAW_JSON = Path.home() / ".openclaw" / "openclaw.json"
MC_API = "http://localhost:8000/api/v1"
MC_AUTH = "28564452b9b917626d3826260fa50fc0648905bb6e4fff85f4904bb248ee43ff"
GW_ID = "c9c74399-6858-46aa-bba8-768cff7e92b6"


def _safe_summary(t: str | None) -> dict:
    if not t or not t.strip():
        return {"length": 0, "first4": "", "last4": "", "empty": True}
    s = t.strip()
    return {
        "length": len(s),
        "first4": s[:4] if len(s) >= 4 else s,
        "last4": s[-4:] if len(s) >= 4 else s,
        "empty": False,
    }


def _write_log(obj: dict) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(obj) + "\n")


def main() -> None:
    run_id = "run1"
    ts = int(__import__("time").time() * 1000)

    # H3: Token from openclaw.json (what the gateway is expected to use if it reads this file)
    openclaw_token = None
    if OPENCLAW_JSON.exists():
        try:
            with open(OPENCLAW_JSON) as f:
                c = json.load(f)
            openclaw_token = (c.get("gateway") or {}).get("auth") or {}
            openclaw_token = openclaw_token.get("token") or ""
        except Exception:
            pass

    openclaw_summary = _safe_summary(openclaw_token)
    _write_log({
        "sessionId": "3c1436",
        "runId": run_id,
        "hypothesisId": "H3",
        "location": "debug_gateway_token_mismatch.py:openclaw",
        "message": "Token from openclaw.json (gateway expected source)",
        "data": {"openclaw_token": openclaw_summary, "openclaw_path": str(OPENCLAW_JSON)},
        "timestamp": ts,
    })

    # H2: Token from Mission Control (what MC sends when it connects to gateway)
    mc_token = None
    try:
        import urllib.request
        req = urllib.request.Request(
            f"{MC_API}/gateways/{GW_ID}",
            headers={"Authorization": f"Bearer {MC_AUTH}"},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            gw = json.loads(resp.read().decode())
            mc_token = gw.get("token") or ""
    except Exception as e:
        _write_log({
            "sessionId": "3c1436",
            "runId": run_id,
            "hypothesisId": "H2",
            "location": "debug_gateway_token_mismatch.py:mc_fetch",
            "message": "MC API fetch failed",
            "data": {"error": str(e)[:200]},
            "timestamp": ts,
        })
        return

    mc_summary = _safe_summary(mc_token)
    match = (
        not openclaw_summary["empty"]
        and not mc_summary["empty"]
        and openclaw_summary["length"] == mc_summary["length"]
        and openclaw_summary["first4"] == mc_summary["first4"]
        and openclaw_summary["last4"] == mc_summary["last4"]
    )
    _write_log({
        "sessionId": "3c1436",
        "runId": run_id,
        "hypothesisId": "H2",
        "location": "debug_gateway_token_mismatch.py:compare",
        "message": "MC token vs openclaw token",
        "data": {
            "openclaw": openclaw_summary,
            "mc": mc_summary,
            "match": match,
            "mismatch_implies": "MC is sending wrong token to gateway" if not match else "tokens_equal",
        },
        "timestamp": ts,
    })

    # H1/H5: Control UI must be opened WITH token in URL
    _write_log({
        "sessionId": "3c1436",
        "runId": run_id,
        "hypothesisId": "H1",
        "location": "debug_gateway_token_mismatch.py:control_ui",
        "message": "Control UI URL must include ?token=...",
        "data": {
            "correct_url_format": "http://127.0.0.1:18789/?token=<gateway_token>",
            "token_in_query_required": True,
            "if_opened_without_token": "gateway returns gateway token mismatch",
        },
        "timestamp": ts,
    })


if __name__ == "__main__":
    main()
