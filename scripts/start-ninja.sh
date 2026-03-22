#!/usr/bin/env bash
# ============================================================
# Start ArbitrageNinja (HFT Agent)
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Default: auto (busca o mercado mais quente do momento)
MARKET_ID=${1:-"auto"}

# Carregar variáveis de ambiente (para acessar DRY_RUN)
echo "Loading env from ~/.openclaw/openclaw.json..."
python3 - <<'PY' > /tmp/clawd-ninja-env.sh
import json, sys, shlex, os
config_path = os.path.expanduser("~/.openclaw/openclaw.json")
try:
    with open(config_path, "r") as f:
        config = json.load(f)
    env = config.get("skills", {}).get("entries", {}).get("polymarket-exec", {}).get("env", {})
except Exception:
    env = {}
for k, v in env.items():
    if v is None or v == "": continue
    print(f"export {k}={shlex.quote(str(v))}")
PY

source /tmp/clawd-ninja-env.sh || true
rm -f /tmp/clawd-ninja-env.sh

cd "$PROJECT_DIR"
echo "==========================================================="
echo " 🥷 Iniciando ArbitrageNinja: Alta Frequência (HFT)"
echo "==========================================================="
echo " Mercado Alvo: $MARKET_ID"
echo " Dry Run: ${DRY_RUN:-true}"
echo "==========================================================="

python3 scripts/agent_ninja_arbitrage.py --market "$MARKET_ID"
