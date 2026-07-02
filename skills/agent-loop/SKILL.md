# Agent Loop Supervisor

Skill para supervisão inteligente dos agentes Clawd via Cursor `/loop`. Complementa o `smart-loop.sh` (24/7 bash) com melhorias, memória e saúde do projeto.

## Arquitetura Híbrida

| Camada | Runtime | Responsabilidade |
|--------|---------|------------------|
| **Operacional** | `scripts/smart-loop.sh` | Trading: PolyClaw → PolyWhale → Executor → Recovery |
| **Supervisor** | Cursor `/loop` + este skill | Skills, memória, git, config sync, melhorias |

Estado compartilhado: `data/loop-state.json`, `data/loop-config.json`, `memory/heartbeat-state.json`

## Ativação no Cursor

### Modo fixo (30 min)

```
/loop 30m Execute skills/agent-loop/SKILL.md — supervisor de agentes
```

### Modo dinâmico (recomendado)

```
/loop Execute skills/agent-loop/SKILL.md em modo dinâmico
```

No modo dinâmico, após cada execução:
- Se `data/loop-state.json` tiver `errors` não vazios → próximo wake em **10 min**
- Se `rateLimited: true` → próximo wake em **45 min**
- Se tudo OK e sem tarefas HEARTBEAT pendentes → **2h**
- Caso padrão → **30 min**

## Prompt do Supervisor (executar a cada tick)

Siga esta sequência em ordem. Seja conciso; faça trabalho real, não apenas relatórios.

### 1. Ler estado do loop operacional

```bash
cat data/loop-state.json
cat data/loop-config.json
```

Verifique: `cycleNumber`, `completedAt`, `phases[]`, `errors[]`, `nextRunAt`, `summary`.

Se `errors` não estiver vazio, priorize diagnóstico e correção antes de melhorias.

### 2. Rotacionar tarefas HEARTBEAT

Leia `HEARTBEAT.md` e `memory/heartbeat-state.json`. Execute **1–2 tarefas** cuja `lastChecks` está mais antiga ou `null`.

Tarefas disponíveis (atualize `lastChecks` após cada uma):

| Chave | Tarefa |
|-------|--------|
| `trade_monitoring` | Revisar `data/executions.jsonl`, recs pendentes, health executor |
| `gateway_health` | `openclaw health`, canais, sessões |
| `config_sync` | `bash scripts/sync-config.sh --to-project` se drift |
| `memory_maintenance` | Revisar daily notes, atualizar `MEMORY.md` (main session) |
| `git_status` | `git status`, organizar mudanças não commitadas |
| `services` | `bash scripts/ensure-running.sh` |
| `polymarket_improvements` | Ler `POLYMARKET_IMPROVEMENTS.md`, fazer 1 melhoria concreta |
| `loop_supervisor` | Revisar smart-loop, ajustar `loop-config.json` se necessário |
| `correction_agent` | Verificar CorrectionAgent (1 instância), fila `approved_corrections.jsonl` |

Atualize `memory/heartbeat-state.json` com timestamp Unix em cada tarefa executada.

### 3. Melhoria Polymarket (se aplicável)

Se `polymarket_improvements` não rodou nas últimas 4h:
1. Ler `POLYMARKET_IMPROVEMENTS.md`
2. Escolher **uma** melhoria concreta (skill doc, código, estratégia)
3. Implementar e documentar em `memory/YYYY-MM-DD.md`

### 4. Verificar serviços críticos

```bash
curl -s http://127.0.0.1:8789/health
curl -s http://localhost:3333/api/loop/status
```

Se smart-loop parado e trading ativo desejado: `bash scripts/start-autoloop.sh`

### 5. Atualizar memória

Append em `memory/YYYY-MM-DD.md`:
- O que o supervisor fez neste tick
- Erros encontrados no loop-state
- Melhorias aplicadas

### 6. Decidir próximo intervalo (modo dinâmico)

| Condição | Próximo wake |
|----------|--------------|
| `errors` no loop-state | 10 min |
| `rateLimited: true` | 45 min |
| Recs pendentes > 0 | 15 min |
| Tudo OK, HEARTBEAT em dia | 2h |
| Padrão | 30 min |

Arm sleep one-shot:
```bash
sleep <seconds>
echo 'AGENT_LOOP_WAKE_supervisor {"prompt":"Execute skills/agent-loop/SKILL.md — supervisor de agentes"}'
```

## Watchers de Eventos (modo dinâmico)

Arme um watcher em background (apenas se não houver um ativo):

```bash
# Acordar quando loop-state mudar
LAST=$(stat -f %m data/loop-state.json 2>/dev/null || stat -c %Y data/loop-state.json)
while true; do
  sleep 30
  NOW=$(stat -f %m data/loop-state.json 2>/dev/null || stat -c %Y data/loop-state.json)
  if [ "$NOW" != "$LAST" ]; then
    echo 'AGENT_LOOP_WAKE_supervisor {"prompt":"Loop-state changed — run agent-loop supervisor"}'
    break
  fi
done
```

Sentinel: `^AGENT_LOOP_WAKE_supervisor`

Watcher secundário para `data/corrections.jsonl` (proposta nova) e `data/approved_corrections.jsonl` (correção aprovada na fila).

## Pipeline de Correções (dashboard)

| Arquivo | Papel |
|---------|-------|
| `data/corrections.jsonl` | Propostas do AutoCorrect (`proposed`) |
| `data/approved_corrections.jsonl` | Aprovadas pelo usuário (`queued`) |
| `data/executed_corrections.jsonl` | Aplicadas pelo CorrectionAgent |

CorrectionAgent: `scripts/correction_agent.py` + `scripts/correction_fixes.py`. Dedupe em `ensure-running.sh` e `start-dashboard-next.sh`.

AutoCorrect roda com `--scan --propose` apenas; não aplica se CorrectionAgent estiver ativo.

## Divisão de Responsabilidades

**NÃO fazer no supervisor** (já feito pelo smart-loop):
- Rodar PolyClaw/PolyWhale/Polybot em ciclo
- Processar recomendações aprovadas
- Brimo check-once / AutoCorrect scan

**FAZER no supervisor**:
- Melhorar skills e documentação
- Curar MEMORY.md
- Sync de config
- Git hygiene
- Diagnosticar erros reportados em loop-state
- Ajustar `loop-config.json` (intervalos, flags)

## Comandos Úteis

```bash
# Status do loop operacional
cat data/loop-state.json | python3 -m json.tool

# Um ciclo manual (sem esperar smart-loop)
bash scripts/smart-loop.sh --once

# Ciclo com lock (dashboard/terminal)
bash scripts/run-agents.sh smart-cycle --with-lock --source manual

# Parar smart-loop
kill $(cat /tmp/clawd-smart-loop.pid 2>/dev/null)

# Iniciar smart-loop
bash scripts/start-autoloop.sh
```

## Roadmap: Integrar LLM nos Agentes Python

Os scripts `agent_polyclaw.py` e `agent_polywhale.py` ainda usam lógica simulada. O supervisor deve, periodicamente:
1. Comparar comportamento dos SKILL.md vs scripts
2. Documentar gaps em `memory/YYYY-MM-DD.md`
3. Propor migração para invocar OpenClaw/skills (fora do escopo automático)

## Referências

- Loop operacional: `scripts/smart-loop.sh`
- Config: `data/loop-config.json`
- Estado: `data/loop-state.json`
- HEARTBEAT: `HEARTBEAT.md`
- Melhorias: `POLYMARKET_IMPROVEMENTS.md`
- Infra: `INFRASTRUCTURE.md`
- Dashboard: `skills/dashboard-next/SKILL.md`
