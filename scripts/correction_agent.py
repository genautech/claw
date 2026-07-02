#!/usr/bin/env python3
"""Daemon that applies approved dashboard corrections."""

import json
import logging
import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.correction_fixes import apply_fix

DATA_DIR = PROJECT_ROOT / "data"
LOG_FILE = DATA_DIR / "approved_corrections.jsonl"
HISTORY_FILE = DATA_DIR / "executed_corrections.jsonl"
LOCK_FILE = DATA_DIR / ".correction_agent.lock"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("CorrectionAgent")


def acquire_lock() -> bool:
    """Ensure only one CorrectionAgent instance runs."""
    DATA_DIR.mkdir(exist_ok=True)
    if LOCK_FILE.exists():
        try:
            pid = int(LOCK_FILE.read_text().strip())
            os.kill(pid, 0)
            return False
        except (OSError, ValueError):
            LOCK_FILE.unlink(missing_ok=True)
    LOCK_FILE.write_text(str(os.getpid()))
    return True


def release_lock() -> None:
    LOCK_FILE.unlink(missing_ok=True)


def _executed_timestamps() -> set[str]:
    if not HISTORY_FILE.exists():
        return set()
    timestamps: set[str] = set()
    for line in HISTORY_FILE.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
            ts = data.get("timestamp")
            if ts:
                timestamps.add(str(ts))
        except json.JSONDecodeError:
            continue
    return timestamps


def process_pending() -> None:
    if not LOG_FILE.exists():
        return

    valid_lines = [line for line in LOG_FILE.read_text().splitlines() if line.strip()]
    if not valid_lines:
        return

    executed = _executed_timestamps()
    new_adds: list[dict] = []

    with HISTORY_FILE.open("a") as history:
        for line in valid_lines:
            try:
                data = json.loads(line)
                ts = data.get("timestamp")
                if not ts or str(ts) in executed:
                    continue

                error_name = data.get("errorName", "Unknown")
                action = data.get("action", "")

                result = apply_fix(error_name, action)
                data["status"] = result.status
                data["result_message"] = result.message
                data["changes"] = result.changes
                data["executed_at"] = time.time()

                history.write(json.dumps(data) + "\n")
                history.flush()
                executed.add(str(ts))
                new_adds.append(data)

                logger.info(
                    "%s: %s (%s)",
                    error_name,
                    result.status,
                    ", ".join(result.changes) if result.changes else "no changes",
                )
            except Exception as exc:
                logger.error("Failed to parse or execute correction line: %s", exc)

    if new_adds:
        logger.info("Processed %s new correction(s).", len(new_adds))


def main() -> None:
    if not acquire_lock():
        logger.error("Another CorrectionAgent is already running. Exiting.")
        sys.exit(1)

    logger.info("Correction Agent started. Listening for approved frontend fixes...")
    try:
        while True:
            try:
                process_pending()
            except KeyboardInterrupt:
                break
            except Exception as exc:
                logger.error("Watcher loop error: %s", exc)
            time.sleep(5)
    finally:
        release_lock()


if __name__ == "__main__":
    main()
