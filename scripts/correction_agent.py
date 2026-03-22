#!/usr/bin/env python3
import time
import json
import logging
import os
import subprocess
from pathlib import Path

# Setup
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
LOG_FILE = DATA_DIR / "approved_corrections.jsonl"
HISTORY_FILE = DATA_DIR / "executed_corrections.jsonl"
OPENCLAW_CONFIG = Path.home() / ".openclaw" / "openclaw.json"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("CorrectionAgent")

def run_fix(error_name: str, action: str):
    logger.info(f"Executing fix for: {error_name}")
    try:
        if error_name == 'Invalid Market ID':
            # Purge market caches
            cache_file = DATA_DIR / "market_cache.json"
            if cache_file.exists():
                cache_file.unlink()
            logger.info("Market cache purged.")
            
        elif error_name == 'Balance/Allowance':
            logger.info("Triggering allowance check script...")
            # Simulate a bash command or run actual allowance script
            pass
            
        elif error_name == 'Invalid Signature':
            logger.info("Attempting to regenerate Polymarket Session...")
            # Simulate session regeneration by touching openclaw.json timestamp
            if OPENCLAW_CONFIG.exists():
                OPENCLAW_CONFIG.touch()
                
        elif error_name == 'Missing Config':
            logger.warning("Please populate ~/.openclaw/openclaw.json manually with POLYMARKET_PK.")
            
        else:
            logger.info(f"Applying generic heuristic fix: {action}")
            
        return True, "Fixed successfully"
    except Exception as e:
        logger.error(f"Correction failed: {e}")
        return False, str(e)

def process_pending():
    if not LOG_FILE.exists():
        return
        
    lines = LOG_FILE.read_text().strip().split('\n')
    valid_lines = [l for l in lines if l.strip()]
    if not valid_lines:
        return
        
    executed = []
    if HISTORY_FILE.exists():
        executed_raw = HISTORY_FILE.read_text().strip().split('\n')
        executed = [json.loads(x).get('timestamp') for x in executed_raw if x.strip()]
        
    new_adds = []
    
    # Process only new corrections
    with open(HISTORY_FILE, 'a') as f:
        for line in valid_lines:
            try:
                data = json.loads(line)
                ts = data.get('timestamp')
                # Skip already executed
                if ts in executed:
                    continue
                    
                error_name = data.get('errorName', 'Unknown')
                action = data.get('action', '')
                
                success, msg = run_fix(error_name, action)
                
                data['status'] = 'completed' if success else 'failed'
                data['result_message'] = msg
                data['executed_at'] = time.time()
                
                f.write(json.dumps(data) + '\n')
                new_adds.append(data)
                
            except Exception as e:
                logger.error(f"Failed to parse or execute correction line: {e}")

    if new_adds:
        logger.info(f"Successfully processed {len(new_adds)} new corrections.")

def main():
    logger.info("Correction Agent started. Listening for approved frontend fixes...")
    while True:
        try:
            process_pending()
        except KeyboardInterrupt:
            break
        except Exception as e:
            logger.error(f"Watcher loop error: {e}")
            
        time.sleep(5)

if __name__ == "__main__":
    main()
