# Quick Start - Polymarket Executor

## 1. Configurar

Edite `~/.openclaw/openclaw.json`:

```json
{
  "skills": {
    "entries": {
      "polymarket-exec": {
        "enabled": true,
        "env": {
          "POLYMARKET_PK": "0x...",
          "POLYMARKET_ADDRESS": "0x...",
          "MAX_TRADE_USD": "100",
          "EXEC_API_TOKEN": "seu-token-seguro"
        }
      }
    }
  }
}
```

## 2. Instalar dependências

```bash
pip install fastapi uvicorn httpx py-clob-client eth-account web3
```

## 3. Iniciar (dry-run primeiro)

```bash
export DRY_RUN=true
bash scripts/start-executor.sh
```

## 4. Testar

```bash
bash scripts/test-executor.sh
```

## 5. Usar

**Via API:**
```bash
curl -X POST http://127.0.0.1:8789/order \
  -H "Authorization: Bearer seu-token" \
  -H "Content-Type: application/json" \
  -d '{"marketId":"0x...","outcomeId":"YES","side":"buy","sizeUsd":50,"maxPrice":0.62}'
```

**Via PolyWhale:**
PolyWhale escreve em `data/recommendations.jsonl`, executor processa automaticamente.

**Via Agente Externo:**
Qualquer agente pode chamar a API local com o token.
