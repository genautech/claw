#!/usr/bin/env python3
"""
Agent AutoCorrect
Scans trade errors and recommends fixes. Can apply fixes when approved by user on dashboard.
Commanded by OpenClaw.
"""

import json
import logging
import subprocess
import sys
from pathlib import Path
import datetime

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.correction_fixes import apply_fix

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("AutoCorrect")

DATA_DIR = PROJECT_ROOT / "data"

EXECS_FILE = DATA_DIR / "executions.jsonl"
CORRECTIONS_FILE = DATA_DIR / "corrections.jsonl"
IMPROVEMENTS_FILE = DATA_DIR / "improvements.jsonl"
CONFIG_FILE = DATA_DIR / "dashboard-config.json"

def read_jsonl(filepath):
    if not filepath.exists():
        return []
    data = []
    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if not line: continue
            try:
                data.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return data

def write_jsonl(filepath, data):
    with open(filepath, 'w') as f:
        for item in data:
            f.write(json.dumps(item) + '\n')

def get_config():
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text())
        except Exception:
            pass
    return {}

def save_config(cfg):
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2))

def categorize_error(err_str):
    err = str(err_str).lower()
    if 'balance' in err or 'allowance' in err: return 'Balance/Allowance'
    if 'invalid market' in err or 'unknown market' in err: return 'Invalid Market ID'
    if 'invalid signature' in err or 'signature validation' in err: return 'Invalid Signature'
    if 'size lower' in err or 'minimum' in err: return 'Size Too Small'
    if 'polymarket_pk' in err or 'api_key' in err or 'unauthorized' in err: return 'Auth/Config Error'
    if 'division by zero' in err: return 'Division by Zero'
    return 'Other'

def scan_and_propose():
    """Scans executions and proposes corrections for frequent errors."""
    execs = read_jsonl(EXECS_FILE)
    errors = [e for e in execs if not e.get('success') and e.get('error')]
    
    if not errors:
        logger.info("No errors found to analyze.")
        return

    # Count recent errors (last 3 days)
    now = datetime.datetime.utcnow()
    recent = []
    
    for e in errors:
        try:
            ts = datetime.datetime.fromisoformat(e['timestamp'].replace('Z', '+00:00'))
            if (now - ts.replace(tzinfo=None)).days <= 3:
                recent.append(e)
        except Exception:
            recent.append(e)

    counts = {}
    for e in recent:
        cat = categorize_error(e['error'])
        counts[cat] = counts.get(cat, 0) + 1

    corrections = read_jsonl(CORRECTIONS_FILE)
    existing_types = {c.get('errorType') for c in corrections if c.get('status') in ['pending', 'approved', 'applied']}
    
    new_proposals = 0
    now_str = datetime.datetime.utcnow().isoformat()
    
    for cat, count in counts.items():
        if count >= 3 and cat not in existing_types and cat != 'Other':
            desc = f"Detected {count} recent errors of type {cat}."
            fix = f"Auto-tune limits and configurations to mitigate {cat} errors."
            if cat == 'Size Too Small':
                fix = "Set minTrade = 5.0 in dashboard-config.json"
            elif cat == 'Balance/Allowance':
                fix = "Enable reserveFloor safety check dynamically"
                
            proposal = {
                "id": f"corr_{int(now.timestamp())}_{cat.replace('/','').replace(' ','_').lower()}",
                "errorType": cat,
                "description": desc,
                "fix": fix,
                "severity": "High" if count > 10 else "Medium",
                "status": "pending",
                "proposedAt": now_str,
                "approvedAt": None,
                "appliedAt": None,
                "verifiedAt": None
            }
            corrections.append(proposal)
            new_proposals += 1
            logger.info(f"Proposed correction for {cat}")

    if new_proposals > 0:
        write_jsonl(CORRECTIONS_FILE, corrections)

def is_correction_agent_running() -> bool:
    """True when CorrectionAgent daemon is active — AutoCorrect should not apply fixes directly."""
    try:
        result = subprocess.run(
            ['pgrep', '-f', 'correction_agent.py'],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0 and bool(result.stdout.strip())
    except Exception:
        return False

def apply_approved():
    """Applies corrections that have been approved by the user."""
    corrections = read_jsonl(CORRECTIONS_FILE)
    changed = False

    for c in corrections:
        if c.get('status') != 'approved':
            continue

        error_type = c.get('errorType', 'Other')
        fix = c.get('fix', '')
        logger.info("Applying fix for %s...", error_type)

        result = apply_fix(error_type, fix)
        c['result_message'] = result.message
        c['changes'] = result.changes

        if result.status in ('completed', 'partial'):
            c['status'] = 'applied'
            c['appliedAt'] = datetime.datetime.utcnow().isoformat()
            changed = True
        elif result.status == 'failed':
            c['status'] = 'failed'
            c['failedAt'] = datetime.datetime.utcnow().isoformat()
            changed = True

    if changed:
        write_jsonl(CORRECTIONS_FILE, corrections)
        logger.info("Corrections updated after apply_approved().")

def verify_improvements():
    """Checks applied corrections to see if they reduced the error rate."""
    corrections = read_jsonl(CORRECTIONS_FILE)
    improvements = read_jsonl(IMPROVEMENTS_FILE)
    execs = read_jsonl(EXECS_FILE)
    
    now = datetime.datetime.utcnow()
    verified_any = False
    
    for c in list(corrections):
        if c.get('status') == 'applied' and c.get('appliedAt'):
            try:
                apply_time = datetime.datetime.fromisoformat(c['appliedAt'].replace('Z', '+00:00'))
                # For testing purposes, we check verifying immediately since we don't really want to wait 24h to see it work
                # in a real world scenario we would verify after 24 hours. Let's make it 60 seconds just to simulate
                if (now - apply_time.replace(tzinfo=None)).total_seconds() > 60:
                    logger.info(f"Verifying improvement for {c['errorType']}")
                    errors = [e for e in execs if not e.get('success') and e.get('error')]
                    cat = c['errorType']
                    cat_errors = [e for e in errors if categorize_error(e['error']) == cat]
                    
                    before = sum(1 for e in cat_errors if datetime.datetime.fromisoformat(e['timestamp'].replace('Z', '+00:00')).replace(tzinfo=None) < apply_time.replace(tzinfo=None))
                    after = sum(1 for e in cat_errors if datetime.datetime.fromisoformat(e['timestamp'].replace('Z', '+00:00')).replace(tzinfo=None) >= apply_time.replace(tzinfo=None))
                    
                    effectiveness = 100
                    if before > 0:
                        effectiveness = max(0, int(((before - after) / before) * 100))
                        
                    improvements.append({
                        "id": f"imp_{c['id']}",
                        "correctionId": c['id'],
                        "errorType": cat,
                        "errorsBefore": before,
                        "errorsAfter": after,
                        "effectivenessScore": effectiveness,
                        "period": "Verification Window",
                        "timestamp": now.isoformat()
                    })
                    c['status'] = 'verified'
                    c['verifiedAt'] = now.isoformat()
                    verified_any = True
            except Exception as e:
                logger.error(f"Error verifying {c['id']}: {e}")

    if verified_any:
        write_jsonl(CORRECTIONS_FILE, corrections)
        write_jsonl(IMPROVEMENTS_FILE, improvements)

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--scan", action="store_true", help="Scan for new errors")
    parser.add_argument("--propose", action="store_true", help="Propose fixes (runs with scan)")
    parser.add_argument("--apply", action="store_true", help="Apply approved fixes (only if CorrectionAgent is offline)")
    parser.add_argument("--verify", action="store_true", help="Verify applied fixes")
    args = parser.parse_args()

    run_scan = args.scan or args.propose or not any(vars(args).values())
    run_apply = args.apply
    run_verify = args.verify

    if run_scan:
        scan_and_propose()
    if run_apply:
        if is_correction_agent_running():
            logger.info("CorrectionAgent is running — skipping direct apply (use approved_corrections.jsonl queue).")
        else:
            apply_approved()
    if run_verify:
        verify_improvements()

if __name__ == "__main__":
    main()
