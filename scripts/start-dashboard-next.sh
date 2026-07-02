#!/usr/bin/env bash
# ============================================================
# PolyClaw Trading Dashboard (Next.js) — porta 3333
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DASHBOARD_DIR="$PROJECT_DIR/dashboard-next"
PORT=3333
ENV_FILE="$DASHBOARD_DIR/.env.local"
LOG_FILE="/tmp/clawd-dashboard-next.log"

echo "Loading env from ~/.openclaw/openclaw.json..."
python3 - <<'PY' > /tmp/clawd-dashboard-env-gen.sh
import json, os, shlex
config_path = os.path.expanduser("~/.openclaw/openclaw.json")
token = ""
try:
    with open(config_path) as f:
        cfg = json.load(f)
    env = cfg.get("skills", {}).get("entries", {}).get("polymarket-exec", {}).get("env", {})
    token = env.get("EXEC_API_TOKEN", "")
except Exception:
    pass
print(f"export EXEC_API_TOKEN={shlex.quote(str(token))}")
PY
# shellcheck disable=SC1091
source /tmp/clawd-dashboard-env-gen.sh || true
rm -f /tmp/clawd-dashboard-env-gen.sh

if [[ -z "${EXEC_API_TOKEN:-}" ]]; then
  echo "⚠️  EXEC_API_TOKEN não encontrado em openclaw.json"
  echo "   Dashboard pode não conseguir ler saldo/posições do executor"
fi

cat > "$ENV_FILE" <<EOF
EXECUTOR_URL=http://127.0.0.1:8789
EXEC_API_TOKEN=${EXEC_API_TOKEN:-change-me-in-production}
EOF
echo "✓ Gerado $ENV_FILE"

if [[ ! -d "$DASHBOARD_DIR/node_modules" ]]; then
  echo "📦 Instalando dependências (npm install)..."
  (cd "$DASHBOARD_DIR" && npm install)
fi

# Prod build artifacts (BUILD_ID + server/pages) poison `next dev` — causes missing chunk errors like ./611.js
is_next_cache_poisoned() {
  [[ -f "$DASHBOARD_DIR/.next/BUILD_ID" && -f "$DASHBOARD_DIR/.next/server/pages/_document.js" ]]
}

clean_next_cache_if_poisoned() {
  if is_next_cache_poisoned; then
    echo "🧹 Removendo .next corrompido (mix dev + npm run build)..."
    rm -rf "$DASHBOARD_DIR/.next"
  fi
}

clean_next_cache_if_poisoned

if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
  if curl -sf -o /dev/null "http://127.0.0.1:$PORT/" 2>/dev/null; then
    echo "⚠️  Dashboard já rodando na porta $PORT"
  else
    echo "⚠️  Dashboard na porta $PORT retornando erro — reiniciando..."
    lsof -Pi :$PORT -sTCP:LISTEN -t | xargs kill 2>/dev/null || true
    sleep 1
    clean_next_cache_if_poisoned
  fi
fi

if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
  :
else
  echo "🚀 Iniciando PolyClaw Trading Dashboard..."
  NEXT_BIN="$DASHBOARD_DIR/node_modules/.bin/next"
  if [[ ! -x "$NEXT_BIN" ]]; then
    echo "❌ Next.js não instalado. Rode: cd dashboard-next && npm install"
    exit 1
  fi
  # Invoca next a partir de dashboard-next (cwd obrigatório para achar app/)
  nohup bash -c "cd \"$DASHBOARD_DIR\" && exec \"$NEXT_BIN\" dev -p $PORT" >> "$LOG_FILE" 2>&1 &
  echo $! > /tmp/clawd-dashboard-next.pid
  echo "   PID: $(cat /tmp/clawd-dashboard-next.pid)"
  echo "   Log: $LOG_FILE"
  sleep 4
  if ! lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "❌ Falha ao iniciar. Últimas linhas do log:"
    tail -15 "$LOG_FILE" 2>/dev/null || true
    exit 1
  fi
fi

# Garantir executor (saldo/posições no dashboard)
if ! lsof -Pi :8789 -sTCP:LISTEN -t >/dev/null 2>&1; then
  echo "🚀 Iniciando Polymarket Executor (porta 8789)..."
  bash "$PROJECT_DIR/scripts/start-executor.sh" || true
fi

# Garantir CorrectionAgent único (aplica correções aprovadas no dashboard)
pkill -f "scripts/correction_agent.py" 2>/dev/null || true
sleep 1
if ! pgrep -f "scripts/correction_agent.py" >/dev/null 2>&1; then
  echo "🚀 Iniciando CorrectionAgent..."
  nohup python3 "$PROJECT_DIR/scripts/correction_agent.py" >> /tmp/correctionagent.log 2>&1 &
  echo "   Log: /tmp/correctionagent.log"
fi

URL="http://127.0.0.1:$PORT"
echo ""
echo "════════════════════════════════════════"
echo "   🦞 PolyClaw Trading Dashboard"
echo "════════════════════════════════════════"
echo ""
echo "   URL: $URL"
echo ""

if command -v open >/dev/null; then
  open "$URL"
fi
