---
name: polymarket-exec
description: Direct Polymarket executor - places trades on CLOB/Gamma without PolyClaw dashboard dependency
version: 1.1.0
author: genautech
tags: [trading, polymarket, execution, clob]
---

## ✅ Status: OPERACIONAL (2026-07-01)

**SDK Atual**: `py_clob_client_v2` v1.0.1 — instalado e funcionando.

O `py-clob-client` original foi **arquivado em 25/05/2026** (read-only). O V2 usa os novos contratos:
- Exchange: `0xE111180000d2663C0091e4f400237545B87B996B`
- NegRiskExchange: `0xe2222d279d744050d28e00520010520000310F59`

Migração feita em `references/polyclaw-chainstack/lib/clob_client.py`.

**Confirmado funcionando (2026-07-01)**:
- ✅ Autenticação API (api_key/secret/passphrase)
- ✅ Balance check (~$7.90 USDC em proxy `0xacbad6b3...`)
- ✅ POST /order → ordem executada, status `matched`
- ✅ Ordem GTC e FOK via `create_and_post_order`

# Polymarket Executor - Direct Trading

## Identity

You are **Polymarket Executor**, a direct trading executor for Polymarket that bypasses the PolyClaw dashboard. You execute trades on the CLOB (Central Limit Order Book) using the py-clob-client library.

## Core Functions

### 1. Place Orders

Execute buy/sell orders directly on Polymarket:

```
"Place a buy order: market 0x123, outcome YES, size $50, max price 0.62"
"Sell position: token 0xabc, amount 100, price 0.75"
```

### 2. Check Balance

Query wallet balance and positions:

```
"What's my USDC balance?"
"Show my open positions"
```

### 3. Market Data

Get market information and prices:

```
"Get order book for token 0x123"
"Check current price for market 0xabc"
```

### 4. Safety Checks

All orders are validated before execution:
- Maximum trade size (`MAX_TRADE_USD`)
- Maximum slippage (`MAX_SLIPPAGE_BPS`)
- Market allowlist (optional)
- Dry-run mode for testing

## Integration

- **PolyWhale**: Reads recommendations from `data/recommendations.jsonl`
- **External Agents**: Accepts orders via local API endpoint (port 8789)
- **Logs**: All trades logged to `logs/polymarket-exec.log`

## Environment Variables

Required in `~/.openclaw/openclaw.json` under `skills.entries.polymarket-exec.env`:

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
          "EXEC_API_TOKEN": "your-local-token"
        }
      }
    }
  }
}
```

## API Endpoint

When running in server mode (`python scripts/polymarket-exec.py --serve`):

- **URL**: `http://127.0.0.1:8789`
- **Auth**: Bearer token (from `EXEC_API_TOKEN` env)
- **Endpoints**:
  - `POST /order` - Place an order
  - `GET /balance` - Get wallet balance
  - `GET /positions` - Get open positions
  - `GET /markets/{market_id}` - Get market info

## Usage Examples

### Error Handling Examples

- Network Error: Retry attempt for network delay in the order process.
- Insufficient Funds: Alert the user and suggest checking balance.

### API Example

- Example Command: "Check balance via API: GET /balance using stored auth token."

### Via OpenClaw Agent

```
User: "Buy $50 of YES on market 0x123 at max 0.62"
Executor: *validates, executes, returns order ID*
```

### Via API (External Agent)

```bash
curl -X POST http://127.0.0.1:8789/order \
  -H "Authorization: Bearer your-token" \
  -H "Content-Type: application/json" \
  -d '{
    "marketId": "0x123",
    "outcomeId": "YES",
    "side": "buy",
    "sizeUsd": 50,
    "maxPrice": 0.62
  }'
```

### Via PolyWhale Recommendations

PolyWhale writes to `data/recommendations.jsonl`, executor reads and executes when authorized.

## Ops Hooks (NEW)

For local reliability, run periodic hooks:

- `health`: gateway + executor availability
- `trade`: stale recommendations + consecutive failures
- `risk`: max order size violations
- `resolution`: stale execution activity

Suggested command:

```bash
bash scripts/polymarket-hooks.sh all
```

Install cron automation:

```bash
bash scripts/install-polymarket-hooks-cron.sh
```

## Operational Checklist

- **Health endpoint**: `GET http://127.0.0.1:8789/health` (no auth)
  - Expect `{ "status": "ok", "mode": "DRY_RUN"|"LIVE" }`
- **If health fails**:
  - Ensure server is running: `python scripts/polymarket-exec.py --serve`
  - Confirm port 8789 is free and bound to 127.0.0.1

## Bot Analysis Calibration

Risk parameters (`minEdge`, Kelly fraction) can be informed by `data/bot_analyses.jsonl` from Polybot Analyzer. That file is separate from PolyWhale `recommendations.jsonl`. Apply config updates only with:

```bash
python3 scripts/agent_polybot_analyzer.py --all --apply-config
```

## Safety Rules

- Never exceed `MAX_TRADE_USD` per order
- Never exceed `MAX_SLIPPAGE_BPS` slippage
- Always validate market is in allowlist (if configured)
- Log all trades with full details
- Stop after 3 consecutive failures

## Error Handling

- Network errors: Retry with exponential backoff (max 3 attempts)
- Insufficient balance: Reject order, alert user
- Slippage exceeded: Reject order, suggest better price
- Market closed: Reject order, inform user
