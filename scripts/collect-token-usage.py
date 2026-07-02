#!/usr/bin/env python3
"""Collect LLM token usage from OpenClaw gateway or log fallback."""

import asyncio
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.absolute()
USAGE_FILE = PROJECT_ROOT / "data" / "token-usage.jsonl"
OPENCLAW_CONFIG = Path.home() / ".openclaw" / "openclaw.json"


def load_gateway_url() -> str:
    try:
        cfg = json.loads(OPENCLAW_CONFIG.read_text())
        port = cfg.get("gateway", {}).get("port", 18789)
        return f"ws://127.0.0.1:{port}"
    except Exception:
        return "ws://127.0.0.1:18789"


def load_gateway_token() -> str | None:
    try:
        cfg = json.loads(OPENCLAW_CONFIG.read_text())
        return (
            cfg.get("gateway", {}).get("auth", {}).get("token")
            or cfg.get("gateway", {}).get("remote", {}).get("token")
        )
    except Exception:
        return os.environ.get("OPENCLAW_GATEWAY_TOKEN")


async def fetch_usage_cost_ws() -> list[dict]:
    """Call usage.cost via OpenClaw gateway WebSocket RPC."""
    try:
        import websockets
    except ImportError:
        return []

    url = load_gateway_url()
    token = load_gateway_token()
    if not token:
        return []

    sep = "&" if "?" in url else "?"
    ws_url = f"{url}{sep}token={token}"

    records: list[dict] = []
    try:
        async with websockets.connect(ws_url, open_timeout=5) as ws:
            req_id = "cost-1"
            await ws.send(
                json.dumps(
                    {
                        "type": "req",
                        "id": req_id,
                        "method": "usage.cost",
                        "params": {},
                    }
                )
            )
            raw = await asyncio.wait_for(ws.recv(), timeout=8)
            msg = json.loads(raw)
            payload = msg.get("result") or msg.get("payload") or msg

            if isinstance(payload, dict):
                entries = payload.get("entries") or payload.get("agents") or [payload]
                if isinstance(entries, dict):
                    entries = [{"agent": k, **(v if isinstance(v, dict) else {})} for k, v in entries.items()]

                for entry in entries if isinstance(entries, list) else []:
                    if not isinstance(entry, dict):
                        continue
                    agent = entry.get("agent") or entry.get("sessionId") or "main"
                    model = entry.get("model") or entry.get("provider") or "unknown"
                    tokens_in = int(entry.get("tokensIn") or entry.get("inputTokens") or entry.get("input", 0) or 0)
                    tokens_out = int(entry.get("tokensOut") or entry.get("outputTokens") or entry.get("output", 0) or 0)
                    cost = float(entry.get("costUsd") or entry.get("cost") or entry.get("totalCost", 0) or 0)
                    records.append(
                        {
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "agent": str(agent).replace("agent:", ""),
                            "model": str(model),
                            "source": "openclaw_gateway",
                            "tokensIn": tokens_in,
                            "tokensOut": tokens_out,
                            "costUsd": cost,
                            "sessionId": entry.get("sessionId"),
                        }
                    )
    except Exception as e:
        print(f"Gateway usage.cost failed: {e}", file=sys.stderr)

    return records


def parse_openclaw_logs() -> list[dict]:
    """Fallback: parse token hints from openclaw log files."""
    records: list[dict] = []
    log_dirs = [Path("/tmp/openclaw"), Path.home() / ".openclaw" / "logs"]
    token_re = re.compile(r"(?P<in>\d+)\s*input.*? (?P<out>\d+)\s*output", re.I)
    model_re = re.compile(r"model[=:\s]+([\w./-]+)", re.I)

    for log_dir in log_dirs:
        if not log_dir.exists():
            continue
        for log_file in sorted(log_dir.glob("*.log"))[-3:]:
            try:
                text = log_file.read_text(errors="ignore")[-50000:]
                for line in text.split("\n"):
                    m = token_re.search(line)
                    if not m:
                        continue
                    model_m = model_re.search(line)
                    records.append(
                        {
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "agent": "main",
                            "model": model_m.group(1) if model_m else "unknown",
                            "source": f"log:{log_file.name}",
                            "tokensIn": int(m.group("in")),
                            "tokensOut": int(m.group("out")),
                            "costUsd": 0,
                            "sessionId": "agent:main:main",
                        }
                    )
            except Exception:
                pass
    return records[-20:]


def append_records(records: list[dict]) -> int:
    if not records:
        return 0
    USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(USAGE_FILE, "a") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
    return len(records)


async def main():
    records = await fetch_usage_cost_ws()
    if not records:
        records = parse_openclaw_logs()
    n = append_records(records)
    print(json.dumps({"ok": True, "appended": n, "source": "gateway" if n and records[0].get("source") == "openclaw_gateway" else "logs"}))


if __name__ == "__main__":
    asyncio.run(main())
