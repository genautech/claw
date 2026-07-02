#!/usr/bin/env python3
"""Set POLYMARKET_PK in ~/.openclaw/openclaw.json after validating it matches the signer."""

import json
import sys
from pathlib import Path

OPENCLAW_CONFIG = Path.home() / ".openclaw" / "openclaw.json"
EXPECTED_SIGNER = "0xe94E3D73E8DFdf4d102beD12293c5aA3e5467C50"


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: set-polymarket-pk.py 0xYOUR_PRIVATE_KEY")
        return 1

    pk = sys.argv[1].strip()
    if not pk.startswith("0x") or len(pk) < 66:
        print("ERROR: expected hex private key like 0x...")
        return 1

    try:
        from eth_account import Account

        derived = Account.from_key(pk).address
    except ImportError:
        print("ERROR: install eth_account: pip install eth-account")
        return 1
    except Exception as exc:
        print(f"ERROR: invalid private key: {exc}")
        return 1

    data = json.loads(OPENCLAW_CONFIG.read_text())
    env = data["skills"]["entries"]["polymarket-exec"]["env"]
    expected = env.get("POLYMARKET_ADDRESS", EXPECTED_SIGNER)

    if derived.lower() != expected.lower():
        print(f"ERROR: key derives {derived}, expected signer {expected}")
        return 1

    env["POLYMARKET_PK"] = pk
    polyclaw = data["skills"]["entries"].setdefault("polyclaw", {})
    polyclaw.setdefault("env", {})["POLYCLAW_PRIVATE_KEY"] = pk

    OPENCLAW_CONFIG.write_text(json.dumps(data, indent=2) + "\n")
    print(f"OK: saved PK for signer {derived}")
    print("Run: python3 scripts/validate-polymarket-config.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
