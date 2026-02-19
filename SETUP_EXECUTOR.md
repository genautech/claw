# Setup Rápido - Polymarket Executor

## ✅ Status Atual

- ✅ Dependências instaladas
- ✅ Executor testado (health check OK)
- ✅ Configuração base criada

## ⚙️ Configuração Necessária

Edite `~/.openclaw/openclaw.json` e adicione as variáveis de ambiente:

```json
{
  "skills": {
    "entries": {
      "polymarket-exec": {
        "enabled": true,
        "env": {
          "POLYMARKET_PK": "0xSUA_CHAVE_PRIVADA_AQUI",
          "POLYMARKET_ADDRESS": "0xSEU_ENDERECO_AQUI",
          "MAX_TRADE_USD": "100",
          "MAX_SLIPPAGE_BPS": "500",
          "EXEC_API_TOKEN": "seu-token-seguro-aqui",
          "DRY_RUN": "true"
        }
      }
    }
  }
}
```

**Onde obter:**
- `POLYMARKET_PK`: Chave privada da sua wallet (mantenha segura!)
- `POLYMARKET_ADDRESS`: Endereço público da wallet (derivado da chave privada)
- `EXEC_API_TOKEN`: Gere um token seguro: `openssl rand -hex 32`

## 🚀 Iniciar

```bash
# Modo dry-run (recomendado primeiro)
export DRY_RUN=true
bash scripts/start-executor.sh

# Modo produção (quando estiver pronto)
export DRY_RUN=false
bash scripts/start-executor.sh
```

## 🧪 Testar

```bash
# Health check
curl http://127.0.0.1:8789/health

# Testar ordem (dry-run)
curl -X POST http://127.0.0.1:8789/order \
  -H "Authorization: Bearer seu-token" \
  -H "Content-Type: application/json" \
  -d '{"marketId":"0x...","outcomeId":"YES","side":"buy","sizeUsd":50,"maxPrice":0.62}'
```

## 📚 Mais Informações

- `README_exec.md` - Documentação completa
- `QUICK_START_EXEC.md` - Guia rápido
- `IMPLEMENTATION_STATUS.md` - Status da implementação
