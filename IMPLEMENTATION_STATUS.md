# Polymarket Executor - Status de Implementação

**Última atualização:** 2026-07-02

## Dashboard Principal

| Dashboard | Porta | Start | Uso |
|-----------|-------|-------|-----|
| **PolyClaw Trading** | **3333** | `bash scripts/start-dashboard-next.sh` | Trades, P&L, aprovação, agentes, hints |
| Clawd Monitoring | 8888 | `bash scripts/start-dashboard.sh` | OpenClaw read-only |
| Mission Control | 3001 | `bash scripts/start-mission-control.sh` | Board de tarefas |

**URL operacional:** http://localhost:3333

### Operações Rápidas (dashboard :3333)

| Botão | O que faz |
|-------|-----------|
| Executar ciclo completo | `run-agents.sh smart-cycle` — 6 fases com lock |
| Smart Loop start/stop | Painel 🧠 Smart Loop — loop 24/7 inteligente |
| Processar aprovados | Envia recs aceitas ao Polymarket via `--process-recs` |
| Analisar bots | `agent_polybot_analyzer.py --all` na watchlist |
| Calibrar minEdge | Aplica edge sugerido em `dashboard-config.json` |
| Verificar latência | Testa Gamma API, executor, Redis |
| Aprovar trade | Aceita rec do PolyWhale + execução imediata |
| Descartar | Rejeita recomendação permanentemente |

Cada botão tem hint (ⓘ) explicando o skill e contexto do trade.

## Agents / Skills

| Componente | Skill | Saída |
|------------|-------|-------|
| PolyClaw | `polyclaw` | `data/simulated_trades.jsonl` |
| PolyWhale | `polywhale` | `data/recommendations.jsonl` |
| Polybot Analyzer | `polybot-analyzer` | `data/bot_analyses.jsonl` |
| Polymarket Executor | `polymarket-exec` | `data/executions.jsonl` |
| Brimo | risk module | `data/risk-events.jsonl` |
| CorrectionAgent | daemon | `data/executed_corrections.jsonl` |
| AutoCorrect | cycle | `data/corrections.jsonl` (propostas) |

## Configuração Polymarket (live)

Arquivo: `~/.openclaw/openclaw.json` → `skills.entries.polymarket-exec.env`

| Variável | Status |
|----------|--------|
| `POLYMARKET_PK` | Configurado |
| `POLYMARKET_PROXY_ADDRESS` | `0xacbad6...032b6` |
| `DRY_RUN` | `false` (live — sincronizado ao salvar no dashboard) |
| `MAX_TRADE_USD` | `2` |
| `MAX_DAILY_EXPOSURE_USD` | `10` |
| Saldo CLOB USDC | ~$12.30 |

`data/dashboard-config.json`: `autoExecute: false`, `dryRun: false`, `minEdge: 5`, `maxTrade: 2`, `maxDailyExposure: 10`, `reserveFloor: 6`

**Modo live com limites:** aprovação manual obrigatória; executor só processa recs `accepted` em `recommendation-status.json`.

## Serviços Locais

| Serviço | Porta | Start |
|---------|-------|-------|
| OpenClaw Gateway | 18789 | `openclaw gateway start` |
| **PolyClaw Trading Dashboard** | **3333** | `bash scripts/start-dashboard-next.sh` |
| Polymarket Executor | 8789 | `bash scripts/start-executor.sh` |
| Autoloop / Smart Loop | — | `bash scripts/start-autoloop.sh` |
| Clawd Monitoring | 8888 | `bash scripts/start-dashboard.sh` |
| Mission Control | 3001 / 8000 | `bash scripts/start-mission-control.sh` |

## Ordem de operação diária

```bash
bash scripts/ensure-running.sh
# Abrir http://localhost:3333
# Iniciar Smart Loop (painel ou terminal):
bash scripts/start-autoloop.sh
# Supervisor Cursor (opcional, com IDE aberto):
# /loop Execute skills/agent-loop/SKILL.md em modo dinâmico
# Revisar recs pendentes → Aprovar/Rejeitar
# Monitorar Brimo (/risk) e posições ativas
# Consultar /bots para calibrar edge
```

## Smart Loop (orquestrador inteligente)

| Arquivo | Função |
|---------|--------|
| `scripts/smart-loop.sh` | Loop 24/7 com 6 fases, lock, intervalo dinâmico |
| `data/loop-config.json` | Intervalo base, min/max, flags de aceleração |
| `data/loop-state.json` | Estado do último ciclo (gerado automaticamente) |
| `skills/agent-loop/SKILL.md` | Supervisor Cursor `/loop` para melhorias e saúde |

**Fases por ciclo:** preflight → arbitrage → analysis → decision → execution → recovery → observability

Alinhado com `run-agents.sh smart-cycle`. Dedupe de múltiplas instâncias em `ensure-running.sh`.

## Performance do Dashboard

| Otimização | Detalhe |
|------------|---------|
| Cache server | `jsonl.ts`, `dataCache.ts`, `aggregates.ts` — invalidação por mtime |
| Endpoints leves | `/api/data?type=summary`, `/api/recommendations?limit=50` |
| Client hook | `useDashboardData` — dedup, staleTime, pausa tab oculta |
| Poll intervals | Home 10s, Sidebar 30s, RealityPanel 5–10s |
| Prod local | `npm run build && npm run start -- -p 3333` (muito mais rápido que `next dev`) |

Skill: `skills/dashboard-next/SKILL.md`

## Pipeline de Correções

| Status API | Significado |
|------------|-------------|
| `proposed` | AutoCorrect propôs; aguarda aprovação em `/analysis` ou `/error-analysis` |
| `queued` | Aprovado; em `approved_corrections.jsonl`; CorrectionAgent aplicará |
| `applied` / `failed` / `partial` | Resultado em `executed_corrections.jsonl` |

Fixes reais: `scripts/correction_fixes.py`. AutoCorrect não aplica se CorrectionAgent estiver ativo.

```bash
# Um ciclo manual (sem loop)
bash scripts/smart-loop.sh --once

# Status via API
curl http://localhost:3333/api/loop/status

# Logs
tail -f /tmp/smart-loop.log
```

## Comandos Úteis

```bash
bash scripts/ensure-running.sh
bash scripts/start-dashboard-next.sh
bash scripts/run-agents.sh all
python3 scripts/agent_polybot_analyzer.py --all --apply-config
python3 scripts/validate-polymarket-config.py
```

## Segurança

- Nunca commitar PK, API secrets ou gateway tokens
- Credenciais em `~/.openclaw/openclaw.json` e `dashboard-next/.env.local` (gitignored)
- `DRY_RUN: true` por padrão até desligar explicitamente no dashboard
