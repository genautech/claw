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
DASHBOARD_PORT=8888
TRADING_DASHBOARD_PORT=3333

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

# 2. PolyClaw Trading Dashboard (Next.js)
echo "2. PolyClaw Trading Dashboard..."
if lsof -Pi :$TRADING_DASHBOARD_PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
  log "Trading Dashboard rodando (porta $TRADING_DASHBOARD_PORT)"
else
  warn "Trading Dashboard não está rodando, iniciando..."
  bash "$PROJECT_DIR/scripts/start-dashboard-next.sh" >/dev/null 2>&1 || true
  sleep 3
  if lsof -Pi :$TRADING_DASHBOARD_PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
    log "Trading Dashboard iniciado (porta $TRADING_DASHBOARD_PORT)"
  else
    err "Falha ao iniciar Trading Dashboard"
  fi
fi
echo ""

# 3. Clawd Monitoring Dashboard (static)
echo "3. Clawd Monitoring Dashboard..."
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

# 5. CorrectionAgent (aplica correções aprovadas no dashboard)
echo "5. CorrectionAgent..."
if pgrep -f "scripts/correction_agent.py" >/dev/null 2>&1; then
  COUNT=$(pgrep -f "scripts/correction_agent.py" | wc -l | tr -d ' ')
  if [[ "$COUNT" -gt 1 ]]; then
    warn "Múltiplas instâncias ($COUNT), reiniciando..."
    pkill -f "scripts/correction_agent.py" 2>/dev/null || true
    sleep 1
  else
    log "CorrectionAgent rodando"
  fi
fi
if ! pgrep -f "scripts/correction_agent.py" >/dev/null 2>&1; then
  warn "CorrectionAgent não está rodando, iniciando..."
  nohup python3 "$PROJECT_DIR/scripts/correction_agent.py" >> /tmp/correctionagent.log 2>&1 &
  sleep 2
  if pgrep -f "scripts/correction_agent.py" >/dev/null 2>&1; then
    log "CorrectionAgent iniciado"
    echo "   Log: /tmp/correctionagent.log"
  else
    err "Falha ao iniciar CorrectionAgent"
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

# Trading Dashboard (principal)
if lsof -Pi :$TRADING_DASHBOARD_PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
  log "PolyClaw Trading Dashboard: ✅ Rodando"
  echo "   URL: http://127.0.0.1:$TRADING_DASHBOARD_PORT"
else
  err "PolyClaw Trading Dashboard: ❌ Parado"
  echo "   Execute: bash scripts/start-dashboard-next.sh"
fi

# Monitoring Dashboard
if lsof -Pi :$DASHBOARD_PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
  log "Clawd Monitoring Dashboard: ✅ Rodando"
  TOKEN=$(openclaw config get gateway.auth.token 2>/dev/null | grep -v "Doctor" | grep -v "^│" | grep -v "^├" | grep -v "^└" | tr -d ' "' || echo "")
  if [[ -n "$TOKEN" ]]; then
    echo "   URL: http://127.0.0.1:$DASHBOARD_PORT/#token=$TOKEN"
  else
    echo "   URL: http://127.0.0.1:$DASHBOARD_PORT"
  fi
else
  err "Clawd Monitoring Dashboard: ❌ Parado"
fi

# Executor
if lsof -Pi :8789 -sTCP:LISTEN -t >/dev/null 2>&1; then
  log "Polymarket Executor: ✅ Rodando"
  echo "   URL: http://127.0.0.1:8789"
  echo "   Health: http://127.0.0.1:8789/health"
else
  warn "Polymarket Executor não está rodando, iniciando..."
  bash "$PROJECT_DIR/scripts/start-executor.sh" >/dev/null 2>&1 || true
  sleep 3
  if lsof -Pi :8789 -sTCP:LISTEN -t >/dev/null 2>&1; then
    log "Polymarket Executor iniciado (porta 8789)"
  else
    echo -e "${YELLOW}⚠️${NC}  Polymarket Executor: ❌ Parado"
    echo "   Execute: bash scripts/start-executor.sh"
  fi
fi
echo ""

# 4. Smart Loop (optional — intelligent agent cycles)
echo "4. Smart Loop (ciclo inteligente)..."
SMART_LOOP_COUNT=$(pgrep -f "scripts/smart-loop.sh" 2>/dev/null | wc -l | tr -d ' ')
if [[ "$SMART_LOOP_COUNT" -gt 1 ]]; then
  warn "Múltiplas instâncias do Smart Loop ($SMART_LOOP_COUNT), reiniciando..."
  pkill -f "scripts/smart-loop.sh" 2>/dev/null || true
  sleep 1
  bash "$PROJECT_DIR/scripts/start-autoloop.sh" >/dev/null 2>&1 || true
  sleep 2
fi
if pgrep -f "scripts/smart-loop.sh" >/dev/null 2>&1; then
  log "Smart Loop rodando"
  echo "   Log: /tmp/smart-loop.log"
  echo "   Estado: data/loop-state.json"
elif pgrep -f "scripts/autoloop.sh" >/dev/null 2>&1; then
  log "Autoloop legado rodando"
  echo "   Log: /tmp/autoloop.log"
else
  warn "Smart Loop não está rodando (opcional)"
  echo "   Execute: bash scripts/start-autoloop.sh"
fi
echo ""

# Mission Control
if lsof -Pi :3001 -sTCP:LISTEN -t >/dev/null 2>&1; then
  log "Mission Control: ✅ Rodando"
  echo "   URL: http://localhost:3001"
  echo "   API: http://localhost:8000/docs"
else
  echo -e "${YELLOW}⚠️${NC}  Mission Control: ❌ Parado"
  echo "   Execute: bash scripts/start-mission-control.sh"
fi

echo ""
echo "════════════════════════════════════════"
echo ""
