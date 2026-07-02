# Polymarket Training Improvements - Agent Instructions

## ✅ RESOLVIDO (2026-07-01)

### Migração para py_clob_client_v2
O `py-clob-client` v0.34.6 foi arquivado em 25/05/2026 (incompatível com novos contratos).
Migração feita para `py_clob_client_v2` v1.0.1 — **ordem de $5 executada com sucesso** (status `matched`).

- SDK novo: `pip install py_clob_client_v2`
- Novos contratos ativos: `0xE111...` (Exchange), `0xe2222...` (NegRiskExchange)
- Arquivo atualizado: `references/polyclaw-chainstack/lib/clob_client.py`

## Your Mission

You are tasked with **proactively improving** the Polymarket trading capabilities of this system. Don't wait to be asked — take initiative and make improvements.

## What to Improve

### 1. Skills Documentation
- Read `skills/polywhale/SKILL.md`, `skills/polymarket-exec/SKILL.md`, `skills/polyclaw/SKILL.md`, `skills/polybot-analyzer/SKILL.md`, `skills/trading-knowledge/index.md`
- Add better examples, clearer instructions, more detailed strategies
- Update with learnings from actual trades
- Fix any unclear or incomplete sections

### 2. Trading Strategies
- Review strategies in `skills/polywhale/SKILL.md`
- Research new strategies from successful traders
- Test strategies on sample markets
- Document what works and what doesn't

### 3. Code Improvements
- Review executor code: `scripts/polymarket-exec.py`
- Optimize for latency, reliability, error handling
- Add better logging, monitoring, safety checks
- Improve integration between PolyWhale and executor

### 4. Integration
- Ensure PolyWhale recommendations flow correctly to executor
- Improve data flow: recommendations.jsonl → executor → executions.jsonl
- Run Polybot Analyzer on watchlist: `python3 scripts/agent_polybot_analyzer.py --all`
- Calibrate `data/dashboard-config.json` from bot analyses (`--apply-config` flag)
- Add monitoring and alerting for trade execution

## How to Do This

1. **During Heartbeats**: Use heartbeat cycles to review and improve
2. **During Sessions**: When working on Polymarket-related tasks, also improve the system
3. **Proactively**: Don't wait — if you see something that can be better, improve it
4. **Document**: Always document what you improved and why

## Examples of Improvements

- ✅ Add more detailed examples to SKILL.md files
- ✅ Update strategies based on market research
- ✅ Improve error handling in executor code
- ✅ Add better logging and monitoring
- ✅ Create test cases for strategies
- ✅ Update documentation with learnings
- ✅ Integrate new ClawHub skills if found

## Remember

- **Be proactive** — don't wait for permission
- **Make it better** — every interaction is a chance to improve
- **Document changes** — write what you did and why
- **Test when possible** — verify improvements work

