# HEARTBEAT.md

# Periodic Autonomy Tasks
# Heartbeat fires every 30 minutes. Use this to check on things proactively.
# Trading cycles are handled by smart-loop.sh — this file focuses on supervision and improvement.

## Coordination with Smart Loop

- **Trading cycles** (PolyClaw, PolyWhale, Executor, Recovery): `scripts/smart-loop.sh` via `bash scripts/start-autoloop.sh`
- **Supervisor tasks** (skills, memory, git): Cursor `/loop` with `skills/agent-loop/SKILL.md`
- **Shared state**: `data/loop-state.json`, `memory/heartbeat-state.json`

Rotate tasks using `memory/heartbeat-state.json` — pick 1–2 tasks with oldest `lastChecks`.

## Project Status
- Check git status for uncommitted changes
- Verify running services (OpenClaw gateway, dashboard, executor, smart-loop)
- Review recent logs for errors (`/tmp/smart-loop.log`, `/tmp/run-agents.log`)

## Memory Maintenance
- Review recent `memory/YYYY-MM-DD.md` files
- Update `MEMORY.md` with significant learnings from daily notes
- Ensure daily notes are being written (smart-loop appends cycle summaries)

## System Health
- Check disk space in workspace
- Verify critical files exist (AGENTS.md, SOUL.md, USER.md, TOOLS.md)
- Review any pending tasks or reminders
- **CorrectionAgent:** `pgrep -f correction_agent.py` — deve haver 1 instância; log em `/tmp/correctionagent.log`
- **Fila de correções:** `data/approved_corrections.jsonl` (queued) e `data/executed_corrections.jsonl` (done)
- **Dashboard perf:** http://localhost:3333 — ver `skills/dashboard-next/SKILL.md`

## Trade Monitoring (read-only — cycles run via smart-loop)
- Read `data/loop-state.json` for last cycle status
- Monitor recent trades in `data/executions.jsonl`
- Review recommendations from PolyWhale in `data/recommendations.jsonl`
- Review bot intelligence in `data/bot_analyses.jsonl` (Polybot Analyzer)
- Check Polymarket executor health: `curl http://127.0.0.1:8789/health`

## Gateway Health
- Monitor OpenClaw gateway status: `openclaw health`
- Check channel connectivity (Telegram, WhatsApp, Discord)
- Verify active sessions count
- Review gateway logs for errors

## Config Sync
- Check if config has drifted between project and live
- Sync if needed: `bash scripts/sync-config.sh --to-project`

## Polymarket Training & Improvement (PRIORITY)
- **Review and improve Polymarket skills**: Read `skills/polywhale/SKILL.md`, `skills/polymarket-exec/SKILL.md`, `skills/polyclaw/SKILL.md`, `skills/polybot-analyzer/SKILL.md`, `skills/trading-knowledge/index.md`
- **Update trading strategies**: Incorporate new learnings from trades, market analysis, and external sources
- **Enhance skill documentation**: Improve SKILL.md files with better examples, clearer instructions, and updated strategies
- **Search ClawHub for new Polymarket skills**: Check if there are better skills available that can be integrated
- **Test and refine**: Run analysis on sample markets, verify strategies work, update code if needed
- **Document improvements**: Write what was learned/improved in `memory/YYYY-MM-DD.md` and update `MEMORY.md` with significant changes

**Action Items:**
1. Read `skills/agent-loop/SKILL.md` for full supervisor workflow
2. Read all Polymarket skill files
3. Identify areas for improvement (strategies, code, documentation)
4. Make improvements proactively (update files, add examples, refine logic)
5. Test improvements if possible
6. Document what was done
