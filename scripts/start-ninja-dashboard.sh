#!/usr/bin/env bash
# ============================================================
# Start ArbitrageNinja Dashboard Server
# Serves the live monitoring dashboard + ninja trade data
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PORT=${1:-8765}

echo "==========================================================="
echo " 🥷 ArbitrageNinja Dashboard Server"
echo "==========================================================="
echo " Dashboard: http://localhost:$PORT"
echo " API:       http://localhost:$PORT/api/ninja/trades"
echo "==========================================================="

cd "$PROJECT_DIR"
python3 scripts/serve-ninja-dashboard.py --port "$PORT"
