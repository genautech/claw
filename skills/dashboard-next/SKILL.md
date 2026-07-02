# Dashboard Next (PolyClaw Trading Dashboard)

Skill para o dashboard local Next.js na porta **3333**. Use ao trabalhar em UI, APIs, performance, botões de ativação de agentes ou fluxo de correções.

## Stack

| Camada | Path |
|--------|------|
| App | `dashboard-next/` |
| Start | `bash scripts/start-dashboard-next.sh` |
| Prod local (perf) | `cd dashboard-next && npm run build && npm run start -- -p 3333` |
| Infra | `INFRASTRUCTURE.md` |

`next dev` é significativamente mais lento — use build+start para testar performance.

## Performance (client)

Hook compartilhado: `dashboard-next/src/hooks/useDashboardData.ts`

- Dedup de requests in-flight (vários componentes, 1 fetch)
- `staleTimeMs` configurável (3–5s típico)
- Pausa polling quando `document.visibilityState === 'hidden'`
- Usado em: Sidebar (30s), RealityPanel (5–10s), error-analysis, arbitrage-ninja

Home (`page.tsx`): `fetch` direto com poll 10s — endpoints leves:
- `GET /api/data?type=summary` (stats + health, sem arrays grandes)
- `GET /api/recommendations?limit=50`

## Performance (server)

| Lib | Função |
|-----|--------|
| `src/lib/jsonl.ts` | `readJsonlTail`, `readJsonlFull`, mtime |
| `src/lib/dataCache.ts` | Cache in-memory com invalidação por mtime + TTL |
| `src/lib/aggregates.ts` | Stats compartilhados entre rotas (`getExecutionsCached`, etc.) |

Endpoints com cache: `/api/data`, `/api/agents` (5s), `/api/recommendations`, `/api/bots`, `/api/error-analysis`.

## Botões → API → Processo

| UI | API | Processo |
|----|-----|----------|
| Toggles agentes (home) | `POST /api/agents` `{ agent, action }` | Ver `AGENT_MAP` em `api/agents/route.ts` |
| Iniciar/Parar Loop | `POST /api/loop/start` \| `stop` | `start-autoloop.sh` → `smart-loop.sh` |
| ArbitrageNinja (RealityPanel) | `POST /api/agents` ArbitrageNinja | `agent_ninja_arbitrage.py --daemon` |
| Ativar modo real | `POST /api/executor/mode` | config executor |
| Executar ciclo completo | `POST /api/agents/run-cycle` | `run-agents.sh smart-cycle` |
| Verificar latência | `POST /api/ops` check-latency | `run-agents.sh ninja` |

### Agentes no AGENT_MAP

PolyClaw, PolyWhale, Polybot, Brimo, CorrectionAgent, AutoCorrect, Executor, ArbitrageNinja, SmartLoop, LatencyNinja.

`ensure-running.sh` auto-inicia: Gateway, dashboard :3333, CorrectionAgent (dedupe), Executor, smart-loop (dedupe). Brimo e ArbitrageNinja são opt-in via UI.

### Status ArbitrageNinja

`/api/realtime` e `/api/agents` usam registry **ou** `pgrep -f agent_ninja_arbitrage.py`. RealityPanel lê `ninjaAgentRunning` de `/api/realtime`.

## Pipeline de correções

```
AutoCorrect (--scan --propose)
  → data/corrections.jsonl (status: proposed)

Usuário aprova (/analysis ou /error-analysis)
  → POST /api/corrections
  → data/approved_corrections.jsonl (status API: queued)

CorrectionAgent (daemon, 1 instância)
  → scripts/correction_fixes.py apply_fix()
  → data/executed_corrections.jsonl (status: applied/failed/partial)
```

Status na API:
- `proposed` — aguardando aprovação humana
- `queued` — aprovado, aguardando CorrectionAgent
- `applied` / `failed` / `partial` / `rejected`

AutoCorrect **não** aplica fixes quando CorrectionAgent está rodando (`pgrep -f correction_agent.py`). Use `--apply` apenas como fallback offline.

## Smart Loop

Fases default (`data/loop-config.json` + `smart-loop.sh`):
`preflight → arbitrage → analysis → decision → execution → recovery → observability`

Igual ao `run-agents.sh smart-cycle`. Acelera intervalo em `approved_corrections.jsonl` e `corrections.jsonl`.

## Verificação rápida

```bash
curl -s http://127.0.0.1:3333/api/loop/status
curl -w "%{time_total}\n" -s -o /dev/null http://127.0.0.1:3333/api/agents
curl -s http://127.0.0.1:3333/api/realtime | python3 -m json.tool
pgrep -fl correction_agent.py
pgrep -fl smart-loop.sh
```

## Referências

- Infra: `INFRASTRUCTURE.md`
- Loops: `skills/agent-loop/SKILL.md`
- Correções: `scripts/correction_agent.py`, `scripts/correction_fixes.py`
