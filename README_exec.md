# Polymarket Direct Executor

Executor direto para Polymarket que não depende do dashboard PolyClaw. Executa trades diretamente no CLOB usando a API do Polymarket.

## Configuração

### 1. Variáveis de Ambiente

Adicione ao `~/.openclaw/openclaw.json`:

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
          "MAX_SLIPPAGE_BPS": "500",
          "EXEC_API_TOKEN": "seu-token-local-seguro",
          "ALLOWED_MARKETS": "0x123,0x456",
          "DRY_RUN": "false"
        }
      }
    }
  }
}
```

**Variáveis:**
- `POLYMARKET_PK`: Chave privada da wallet (0x...)
- `POLYMARKET_ADDRESS`: Endereço da wallet (0x...)
- `MAX_TRADE_USD`: Tamanho máximo por ordem (padrão: 100)
- `MAX_SLIPPAGE_BPS`: Slippage máximo em basis points (500 = 5%)
- `EXEC_API_TOKEN`: Token para autenticação da API local
- `ALLOWED_MARKETS`: Lista de market IDs permitidos (opcional, separado por vírgula)
- `DRY_RUN`: "true" para simular sem executar (padrão: "false")

### 2. Instalar Dependências

```bash
pip install fastapi uvicorn httpx py-clob-client eth-account web3
```

Ou use o requirements do projeto:

```bash
cd references/polyclaw-chainstack
pip install -r requirements.txt
```

## Uso

### Modo API (Recomendado)

Inicie o servidor:

```bash
python scripts/polymarket-exec.py --serve --port 8789 --token seu-token
```

Ou use a variável de ambiente:

```bash
export EXEC_API_TOKEN=seu-token
python scripts/polymarket-exec.py --serve --port 8789
```

### Colocar uma Ordem

```bash
curl -X POST http://127.0.0.1:8789/order \
  -H "Authorization: Bearer seu-token" \
  -H "Content-Type: application/json" \
  -d '{
    "marketId": "0x123...",
    "outcomeId": "YES",
    "side": "buy",
    "sizeUsd": 50,
    "maxPrice": 0.62
  }'
```

**Resposta:**
```json
{
  "success": true,
  "order_id": "0xabc...",
  "token_id": "0xdef...",
  "token_amount": 80.65,
  "price": 0.62,
  "size_usd": 50
}
```

### Verificar Saldo

```bash
curl http://127.0.0.1:8789/balance \
  -H "Authorization: Bearer seu-token"
```

### Ver Posições

```bash
curl http://127.0.0.1:8789/positions \
  -H "Authorization: Bearer seu-token"
```

### Obter Info do Mercado

```bash
curl http://127.0.0.1:8789/markets/0x123... \
  -H "Authorization: Bearer seu-token"
```

## Integração com PolyWhale

O PolyWhale pode escrever recomendações em `data/recommendations.jsonl`:

```json
{"id": "rec_1", "market_id": "0x123", "decision": "BUY_YES", "targetPrice": 0.62, "risk_pct": 0.05}
```

Processar recomendações:

```bash
python scripts/polymarket-exec.py --process-recs
```

## Integração com Agente Externo

Qualquer agente externo pode chamar a API local:

```python
import requests

API_URL = "http://127.0.0.1:8789"
TOKEN = "seu-token"

response = requests.post(
    f"{API_URL}/order",
    headers={"Authorization": f"Bearer {TOKEN}"},
    json={
        "marketId": "0x123",
        "outcomeId": "YES",
        "side": "buy",
        "sizeUsd": 50,
        "maxPrice": 0.62
    }
)
print(response.json())
```

## Safety Checks

O executor valida todas as ordens antes de executar:

- ✅ Tamanho máximo por ordem (`MAX_TRADE_USD`)
- ✅ Slippage máximo (`MAX_SLIPPAGE_BPS`)
- ✅ Lista de mercados permitidos (se configurado)
- ✅ Preço dentro dos limites [0.01, 0.99]
- ✅ Para após 3 falhas consecutivas

## Modo Dry-Run

Para testar sem executar trades reais:

```bash
export DRY_RUN=true
python scripts/polymarket-exec.py --serve --port 8789
```

Todas as ordens serão simuladas e não executadas no CLOB.

## Logs

Todos os trades são logados em:
- `logs/polymarket-exec.log` - Log detalhado
- `data/executions.jsonl` - Histórico de execuções

## Troubleshooting

**Erro: "POLYMARKET_PK not set"**
- Configure a variável de ambiente ou no `openclaw.json`

**Erro: "Order size exceeds max"**
- Aumente `MAX_TRADE_USD` ou reduza o tamanho da ordem

**Erro: "Slippage exceeds max"**
- Aumente `MAX_SLIPPAGE_BPS` ou ajuste o `maxPrice`

**Erro: "Executor stopped after 3 failures"**
- Reinicie o executor ou verifique os logs para identificar o problema

## Segurança

- ⚠️ **NUNCA** compartilhe sua `POLYMARKET_PK`
- ⚠️ Use um token forte para `EXEC_API_TOKEN`
- ⚠️ Configure `ALLOWED_MARKETS` para limitar quais mercados podem ser negociados
- ⚠️ Use `DRY_RUN=true` para testar antes de executar trades reais
