#!/usr/bin/env python3
"""Validate Polymarket executor configuration in ~/.openclaw/openclaw.json."""

import json
import os
import sys
from pathlib import Path

OPENCLAW_CONFIG = Path.home() / ".openclaw" / "openclaw.json"
SIGNER = "0xe94E3D73E8DFdf4d102beD12293c5aA3e5467C50"
PROXY = "0xacbad6b3e3e7f793b3efa72161d91c52e80332b6"


def load_env() -> dict:
    if not OPENCLAW_CONFIG.exists():
        raise FileNotFoundError(f"Missing config: {OPENCLAW_CONFIG}")
    data = json.loads(OPENCLAW_CONFIG.read_text())
    return data.get("skills", {}).get("entries", {}).get("polymarket-exec", {}).get("env", {})


def main() -> int:
    env = load_env()
    pk = env.get("POLYMARKET_PK", "")
    address = env.get("POLYMARKET_ADDRESS", "")
    proxy = env.get("POLYMARKET_PROXY_ADDRESS", "")

    print("Polymarket config status")
    print("=" * 40)
    for key in [
        "POLYMARKET_ADDRESS",
        "POLYMARKET_PROXY_ADDRESS",
        "POLYMARKET_PK",
        "POLYMARKET_API_KEY",
        "POLYMARKET_API_SECRET",
        "POLYMARKET_API_PASSPHRASE",
        "EXEC_API_TOKEN",
        "DRY_RUN",
    ]:
        value = env.get(key, "")
        status = "OK" if value else "MISSING"
        print(f"{key}: {status}")

    if address.lower() != SIGNER.lower():
        print(f"\nWARN: POLYMARKET_ADDRESS expected {SIGNER}, got {address or '(empty)'}")
    if proxy.lower() != PROXY.lower():
        print(f"WARN: POLYMARKET_PROXY_ADDRESS expected {PROXY}, got {proxy or '(empty)'}")

    if pk:
        try:
            from eth_account import Account

            derived = Account.from_key(pk).address
            if derived.lower() != address.lower():
                print(f"\nERROR: PK derives {derived}, not {address}")
                return 1
            print(f"\nOK: PK matches signer address {derived}")
        except ImportError:
            print("\nWARN: eth_account not installed; skipped PK/address check")
        except Exception as exc:
            print(f"\nERROR: invalid PK: {exc}")
            return 1
    else:
        print("\nBLOCKED: POLYMARKET_PK still missing.")
        print("Export the private key from the wallet that owns:")
        print(f"  {SIGNER}")
        print("Then set it in ~/.openclaw/openclaw.json under:")
        print("  skills.entries.polymarket-exec.env.POLYMARKET_PK")
        return 1

    print("\nReady for dry-run executor.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
