#!/usr/bin/env bash
# ============================================================
# Ensure All Services Running
# ============================================================
# Verifica e inicia todos os serviços do ClawdBot
# ============================================================

set -euo pipefail

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log()  { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
err()  { echo -e "${RED}[✗]${NC} $1"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DASHBOARD_PORT=8787

echo "🔍 Verificando serviços..."
echo ""

# 1. OpenClaw Gateway
echo "1. OpenClaw Gateway..."
if openclaw gateway health >/dev/null 2>&1; then
  HEALTH=$(openclaw gateway health 2>/dev/null | grep -E "OK|Error" | head -1)
  if echo "$HEALTH" | grep -q "OK"; then
    log "Gateway rodando (porta 18789)"
    openclaw gateway health 2>/dev/null | grep -E "Telegram|WhatsApp|Discord" | sed 's/^/   /'
  else
    err "Gateway com problemas"
    warn "Tentando reiniciar..."
    openclaw gateway restart 2>/dev/null || true
    sleep 3
    if openclaw gateway health >/dev/null 2>&1; then
      log "Gateway reiniciado com sucesso"
    else
      err "Falha ao reiniciar gateway"
    fi
  fi
else
  warn "Gateway não está rodando, iniciando..."
  openclaw gateway start 2>/dev/null || true
  sleep 3
  if openclaw gateway health >/dev/null 2>&1; then
    log "Gateway iniciado"
  else
    err "Falha ao iniciar gateway"
  fi
fi
echo ""

# 2. Dashboard
echo "2. Clawd Dashboard..."
if lsof -Pi :$DASHBOARD_PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
  log "Dashboard rodando (porta $DASHBOARD_PORT)"
else
  warn "Dashboard não está rodando, iniciando..."
  cd "$PROJECT_DIR/dashboard-web"
  python3 -m http.server $DASHBOARD_PORT > /tmp/clawd-dashboard.log 2>&1 &
  sleep 2
  if lsof -Pi :$DASHBOARD_PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
    log "Dashboard iniciado (porta $DASHBOARD_PORT)"
  else
    err "Falha ao iniciar dashboard"
  fi
fi
echo ""

# 3. Resumo
echo "════════════════════════════════════════"
echo "   📊 Status dos Serviços"
echo "════════════════════════════════════════"
echo ""

# Gateway
if openclaw gateway health >/dev/null 2>&1; then
  log "OpenClaw Gateway: ✅ Rodando"
  echo "   URL: http://127.0.0.1:18789"
  echo "   Chat: http://127.0.0.1:18789/chat?session=agent%3Amain%3Amain"
else
  err "OpenClaw Gateway: ❌ Parado"
fi

# Dashboard
if lsof -Pi :$DASHBOARD_PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
  log "Clawd Dashboard: ✅ Rodando"
  TOKEN=$(openclaw config get gateway.auth.token 2>/dev/null | grep -v "Doctor" | grep -v "^│" | grep -v "^├" | grep -v "^└" | tr -d ' "' || echo "")
  if [[ -n "$TOKEN" ]]; then
    echo "   URL: http://127.0.0.1:$DASHBOARD_PORT/#token=$TOKEN"
  else
    echo "   URL: http://127.0.0.1:$DASHBOARD_PORT"
  fi
else
  err "Clawd Dashboard: ❌ Parado"
fi

# Executor
if lsof -Pi :8789 -sTCP:LISTEN -t >/dev/null 2>&1; then
  log "Polymarket Executor: ✅ Rodando"
  echo "   URL: http://127.0.0.1:8789"
  echo "   Health: http://127.0.0.1:8789/health"
else
  echo -e "${YELLOW}⚠️${NC}  Polymarket Executor: ❌ Parado"
  echo "   Execute: bash scripts/start-executor.sh"
  echo "   ${YELLOW}   Nota:${NC} Requer POLYMARKET_PK e POLYMARKET_ADDRESS"
fi

echo ""
echo "════════════════════════════════════════"
echo ""
