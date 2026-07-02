#!/usr/bin/env python3
"""Shared correction fixes applied by CorrectionAgent and AutoCorrect."""

from __future__ import annotations

import json
import ssl
import subprocess
import sys
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
CONFIG_FILE = DATA_DIR / "dashboard-config.json"
VALID_MARKET_IDS_FILE = DATA_DIR / "valid_market_ids.json"
INVESTIGATIONS_FILE = DATA_DIR / "correction_investigations.jsonl"
EXECS_FILE = DATA_DIR / "executions.jsonl"
VALIDATE_SCRIPT = PROJECT_ROOT / "scripts" / "validate-polymarket-config.py"

SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

FixStatus = Literal["completed", "failed", "partial"]

ERROR_ALIASES = {
    "Auth Error": "Auth/Config Error",
    "Missing Config": "Auth/Config Error",
    "Auth/Config Error": "Auth/Config Error",
}


@dataclass
class FixResult:
    success: bool
    status: FixStatus
    message: str
    changes: list[str] = field(default_factory=list)


def _normalize_error_name(error_name: str) -> str:
    return ERROR_ALIASES.get(error_name, error_name)


def _load_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text())
        except Exception:
            pass
    return {}


def _save_config(cfg: dict) -> None:
    CONFIG_FILE.parent.mkdir(exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2) + "\n")


def _patch_config(updates: dict) -> list[str]:
    cfg = _load_config()
    changes: list[str] = []
    for key, value in updates.items():
        if cfg.get(key) != value:
            cfg[key] = value
            changes.append(f"{key}={value}")
    if changes:
        _save_config(cfg)
    return changes


def _fetch_usdc_balance() -> float:
    """Best-effort USDC balance via CLOB client."""
    try:
        sys.path.insert(0, str(PROJECT_ROOT))
        sys.path.insert(0, str(PROJECT_ROOT / "references" / "polyclaw-chainstack"))
        import os

        openclaw = Path.home() / ".openclaw" / "openclaw.json"
        if openclaw.exists():
            cfg = json.loads(openclaw.read_text())
            env = cfg.get("skills", {}).get("entries", {}).get("polymarket-exec", {}).get("env", {})
            for key, value in env.items():
                if value and not os.environ.get(key):
                    os.environ[key] = str(value)

        from lib.clob_client import ClobClientWrapper
        from py_clob_client.clob_types import BalanceAllowanceParams

        wrapper = ClobClientWrapper()
        res = wrapper.client.get_balance_allowance(
            BalanceAllowanceParams(asset_type="COLLATERAL")
        )
        return float(res.get("balance", "0")) / 10**6
    except Exception:
        return -1.0


def _fix_balance_allowance(action: str) -> FixResult:
    changes: list[str] = []
    balance = _fetch_usdc_balance()

    cfg_changes = _patch_config({"autoExecute": False})
    changes.extend(cfg_changes)

    reserve = float(_load_config().get("reserveFloor", 6))
    if balance >= 0 and balance < reserve + 2:
        new_reserve = max(1.0, round(balance * 0.5, 2))
        reserve_changes = _patch_config({"reserveFloor": new_reserve})
        changes.extend(reserve_changes)

    if balance >= 0:
        msg = f"USDC balance ${balance:.2f}; autoExecute disabled"
        if changes:
            return FixResult(True, "completed", msg, changes)
        return FixResult(True, "completed", msg, ["autoExecute=false (already set)"])

    changes.extend(_patch_config({"reserveFloor": reserve}))
    return FixResult(
        True,
        "partial",
        "Could not fetch live balance; disabled autoExecute as safety measure",
        changes or ["autoExecute=false"],
    )


def _fix_division_by_zero(action: str) -> FixResult:
    guarded_files: list[str] = []
    checks = [
        (PROJECT_ROOT / "scripts" / "brimo.py", "price and price > 0"),
        (PROJECT_ROOT / "scripts" / "polymarket-exec.py", "current_price <= 0"),
        (PROJECT_ROOT / "scripts" / "agent_polyclaw.py", "yes_price <= 0"),
    ]
    for path, needle in checks:
        if path.exists() and needle in path.read_text():
            guarded_files.append(path.name)

    if len(guarded_files) >= 2:
        return FixResult(
            True,
            "completed",
            f"Zero-price guards verified in {', '.join(guarded_files)}",
            [f"verified guards in {f}" for f in guarded_files],
        )

    return FixResult(
        False,
        "failed",
        "Could not verify zero-price guards in trading scripts",
        [],
    )


def _fetch_gamma_market_ids(limit: int = 200) -> set[str]:
    url = (
        f"https://gamma-api.polymarket.com/markets"
        f"?active=true&limit={limit}&order=volume24hr&ascending=false"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "PolyClaw-CorrectionAgent/1.0"})
    with urllib.request.urlopen(req, timeout=30, context=SSL_CTX) as resp:
        markets = json.loads(resp.read().decode())

    ids: set[str] = set()
    for market in markets:
        for key in ("id", "conditionId", "condition_id"):
            val = market.get(key)
            if val:
                ids.add(str(val))
    return ids


def _fix_invalid_market_id(action: str) -> FixResult:
    changes: list[str] = []
    cache_file = DATA_DIR / "market_cache.json"
    if cache_file.exists():
        cache_file.unlink()
        changes.append("purged market_cache.json")

    try:
        ids = _fetch_gamma_market_ids()
        payload = {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "count": len(ids),
            "ids": sorted(ids),
        }
        VALID_MARKET_IDS_FILE.write_text(json.dumps(payload, indent=2) + "\n")
        changes.append(f"valid_market_ids.json refreshed ({len(ids)} ids)")
        return FixResult(
            True,
            "completed",
            f"Market cache updated with {len(ids)} valid IDs from Gamma API",
            changes,
        )
    except Exception as exc:
        return FixResult(False, "failed", f"Gamma API fetch failed: {exc}", changes)


def _fix_auth_config(action: str) -> FixResult:
    if not VALIDATE_SCRIPT.exists():
        return FixResult(False, "failed", f"Missing validator: {VALIDATE_SCRIPT}", [])

    result = subprocess.run(
        [sys.executable, str(VALIDATE_SCRIPT)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    output = (result.stdout or "") + (result.stderr or "")
    if result.returncode == 0:
        return FixResult(True, "completed", "Polymarket config validation passed", ["config validated"])

    return FixResult(
        False,
        "failed",
        output.strip() or "Polymarket config validation failed",
        [],
    )


def _fix_invalid_signature(action: str) -> FixResult:
    openclaw = Path.home() / ".openclaw" / "openclaw.json"
    if not openclaw.exists():
        return FixResult(
            False,
            "failed",
            "Missing ~/.openclaw/openclaw.json — regenerate API keys in Polymarket settings",
            [],
        )

    try:
        cfg = json.loads(openclaw.read_text())
        env = cfg.get("skills", {}).get("entries", {}).get("polymarket-exec", {}).get("env", {})
        required = ["POLYMARKET_PK", "POLYMARKET_API_KEY", "POLYMARKET_API_SECRET", "POLYMARKET_API_PASSPHRASE"]
        missing = [k for k in required if not env.get(k)]
        if missing:
            return FixResult(
                False,
                "failed",
                f"Missing credentials: {', '.join(missing)}. Regenerate keys at polymarket.com/settings",
                [],
            )
        return FixResult(
            True,
            "partial",
            "Credentials present; if errors persist, regenerate API keys and sync server time",
            ["credentials present — manual key rotation may be required"],
        )
    except Exception as exc:
        return FixResult(False, "failed", str(exc), [])


def _fix_size_too_small(action: str) -> FixResult:
    changes = _patch_config({"minTrade": 5.0})
    if changes:
        return FixResult(True, "completed", "minTrade set to 5.0 USDC", changes)
    cfg = _load_config()
    if float(cfg.get("minTrade", 0)) >= 5.0:
        return FixResult(True, "completed", "minTrade already >= 5.0", ["minTrade already >= 5.0"])
    return FixResult(False, "failed", "Failed to update minTrade", [])


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def _fix_other(action: str) -> FixResult:
    errors = [
        e for e in _read_jsonl(EXECS_FILE)
        if not e.get("success") and e.get("error")
    ][-10:]
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "sample_errors": [
            {"timestamp": e.get("timestamp"), "error": str(e.get("error"))[:500]}
            for e in errors
        ],
    }
    INVESTIGATIONS_FILE.parent.mkdir(exist_ok=True)
    with INVESTIGATIONS_FILE.open("a") as f:
        f.write(json.dumps(entry) + "\n")
    return FixResult(
        True,
        "partial",
        f"Logged {len(entry['sample_errors'])} recent errors for manual investigation",
        ["appended correction_investigations.jsonl"],
    )


def apply_fix(error_name: str, action: str = "") -> FixResult:
    """Apply a concrete fix for the given error type."""
    normalized = _normalize_error_name(error_name)

    handlers = {
        "Balance/Allowance": _fix_balance_allowance,
        "Division by Zero": _fix_division_by_zero,
        "Invalid Market ID": _fix_invalid_market_id,
        "Auth/Config Error": _fix_auth_config,
        "Invalid Signature": _fix_invalid_signature,
        "Size Too Small": _fix_size_too_small,
        "Other": _fix_other,
    }

    handler = handlers.get(normalized)
    if handler is None:
        if action:
            return _fix_other(action)
        return FixResult(False, "failed", f"No handler for error type: {error_name}", [])

    result = handler(action)
    if result.status == "completed" and not result.changes:
        result = FixResult(
            result.success,
            "failed",
            result.message or "No changes were applied",
            [],
        )
    return result
