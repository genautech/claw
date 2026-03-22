#!/usr/bin/env bash
# ============================================================
# Check ClawdBot Status
# ============================================================

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo "🔍 Verificando status do ClawdBot..."
echo ""

# Gateway
echo "1. OpenClaw Gateway:"
if openclaw gateway health >/dev/null 2>&1; then
  echo -e "${GREEN}   ✅ Gateway rodando${NC}"
  openclaw gateway health 2>/dev/null | grep -E "Telegram|WhatsApp|Discord" | sed 's/^/   /'
else
  echo -e "${RED}   ❌ Gateway parado${NC}"
fi
echo ""

# Skills
echo "2. Skills configurados:"
SKILLS=$(openclaw config get skills.entries 2>/dev/null | python3 -c "import json,sys; d=json.load(sys.stdin); print('\n'.join([f'{k}: {\"enabled\" if v.get(\"enabled\", True) else \"disabled\"}' for k,v in d.items()]))" 2>/dev/null)
if [ -n "$SKILLS" ]; then
  echo "$SKILLS" | sed 's/^/   ✅ /'
else
  echo -e "${YELLOW}   ⚠️  Não foi possível verificar skills${NC}"
fi
echo ""

# Workspace Skills
echo "3. Skills do workspace:"
for skill in polywhale latencyninja configdash; do
  if [ -f "$HOME/.openclaw/workspace/skills/$skill/SKILL.md" ]; then
    echo -e "   ${GREEN}✅${NC} $skill"
  else
    echo -e "   ${RED}❌${NC} $skill (não encontrado)"
  fi
done
echo ""

# Channels
echo "4. Canais:"
openclaw channels status 2>/dev/null | grep -E "Telegram|WhatsApp|Discord" | sed 's/^/   /' || echo "   Não foi possível verificar"
echo ""

# Dashboard
echo "5. Dashboard:"
if lsof -Pi :8888 -sTCP:LISTEN -t >/dev/null 2>&1; then
  echo -e "   ${GREEN}✅${NC} Rodando na porta 8888"
  TOKEN=$(openclaw config get gateway.auth.token 2>/dev/null | grep -v "Doctor" | grep -v "^│" | grep -v "^├" | grep -v "^└" | tr -d ' "' || echo "")
  if [ -n "$TOKEN" ]; then
    echo "   URL: http://127.0.0.1:8888/#token=$TOKEN"
  else
    echo "   URL: http://127.0.0.1:8888"
  fi
else
  echo -e "   ${YELLOW}⚠️${NC}  Não está rodando (execute: bash scripts/start-dashboard.sh)"
fi
echo ""

echo "════════════════════════════════════════"
echo ""
