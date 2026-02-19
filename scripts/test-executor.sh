#!/usr/bin/env bash
# ============================================================
# Test Polymarket Executor
# ============================================================

set -euo pipefail

API_URL="http://127.0.0.1:8789"
TOKEN="${EXEC_API_TOKEN:-test-token-change-me}"

echo "🧪 Testando Polymarket Executor..."
echo ""

# Test health
echo "1. Health check:"
curl -s "$API_URL/health" | python3 -m json.tool || echo "❌ Servidor não está rodando"
echo ""

# Test balance (requires auth)
echo "2. Balance check (com token):"
curl -s "$API_URL/balance" \
  -H "Authorization: Bearer $TOKEN" \
  | python3 -m json.tool 2>/dev/null || echo "⚠️  Requer token válido"
echo ""

# Test market info (example market ID)
echo "3. Market info (exemplo):"
echo "   Use: curl $API_URL/markets/0x... -H 'Authorization: Bearer \$TOKEN'"
echo ""

# Test order (dry-run)
echo "4. Test order (dry-run recomendado primeiro):"
echo "   curl -X POST $API_URL/order \\"
echo "     -H 'Authorization: Bearer \$TOKEN' \\"
echo "     -H 'Content-Type: application/json' \\"
echo "     -d '{\"marketId\":\"0x...\",\"outcomeId\":\"YES\",\"side\":\"buy\",\"sizeUsd\":50,\"maxPrice\":0.62}'"
echo ""

echo "✅ Testes concluídos"
echo ""
echo "Nota: Configure EXEC_API_TOKEN ou use --token ao iniciar o executor"
