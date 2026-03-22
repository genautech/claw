#!/usr/bin/env python3
"""
Try to approve the pending OpenClaw gateway device via WebSocket RPC.

The gateway may reject with "missing scope: operator.pairing" when connecting
with only the auth token. If that happens, approve the device manually:

1. Open the Control UI: http://127.0.0.1:18789/?token=YOUR_GATEWAY_TOKEN
2. Find the "Devices" or "Pairing" section and approve the pending request.

Gateway token is in ~/.openclaw/openclaw.json under gateway.auth.token.
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from uuid import uuid4

try:
    import websockets
except ImportError:
    print("Install websockets: pip install websockets", file=sys.stderr)
    sys.exit(1)

OPENCLAW_STATE = Path(os.environ.get("OPENCLAW_STATE_DIR", Path.home() / ".openclaw"))
DEVICES_PENDING = OPENCLAW_STATE / "devices" / "pending.json"
OPENCLAW_JSON = OPENCLAW_STATE / "openclaw.json"


def get_gateway_token():
    if not OPENCLAW_JSON.exists():
        return None
    data = json.loads(OPENCLAW_JSON.read_text())
    auth = (data.get("gateway") or {}).get("auth") or {}
    return auth.get("token")


def get_pending_request_ids():
    if not DEVICES_PENDING.exists():
        return []
    data = json.loads(DEVICES_PENDING.read_text())
    if isinstance(data, dict):
        return [v.get("requestId") for v in data.values() if v.get("requestId")]
    return []


async def approve_via_ws(request_id: str, token: str, gateway_url: str = "ws://127.0.0.1:18789"):
    url = f"{gateway_url}?token={token}"
    async with websockets.connect(url, ping_interval=None) as ws:
        await asyncio.wait_for(ws.recv(), timeout=3)
        connect_id = str(uuid4())
        await ws.send(
            json.dumps(
                {
                    "type": "req",
                    "id": connect_id,
                    "method": "connect",
                    "params": {
                        "minProtocol": 3,
                        "maxProtocol": 3,
                        "role": "operator",
                        "scopes": [
                            "operator.read",
                            "operator.admin",
                            "operator.approvals",
                            "operator.pairing",
                        ],
                        "client": {
                            "id": "gateway-client",
                            "version": "1.0.0",
                            "platform": "web",
                            "mode": "ui",
                        },
                        "auth": {"token": token},
                    },
                }
            )
        )
        conn_resp = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
        if not conn_resp.get("ok"):
            print("Connect failed:", conn_resp, file=sys.stderr)
            return False
        req_id = str(uuid4())
        await ws.send(
            json.dumps(
                {
                    "type": "req",
                    "id": req_id,
                    "method": "device.pair.approve",
                    "params": {"requestId": request_id},
                }
            )
        )
        approve_resp = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
        return approve_resp.get("ok"), approve_resp


def main():
    token = get_gateway_token()
    if not token:
        print("Could not read gateway token from", OPENCLAW_JSON, file=sys.stderr)
        sys.exit(1)
    request_ids = get_pending_request_ids()
    if not request_ids:
        print("No pending device requests in", DEVICES_PENDING, file=sys.stderr)
        sys.exit(0)
    request_id = request_ids[0]
    ok, resp = asyncio.run(approve_via_ws(request_id, token))
    if ok:
        print("Approved device request", request_id)
        return
    err = (resp.get("error") or {}).get("message", resp)
    print("Approval failed:", err, file=sys.stderr)
    print("\nApprove manually: open http://127.0.0.1:18789/?token=... and approve the pending device in the UI.")
    sys.exit(1)


if __name__ == "__main__":
    main()
