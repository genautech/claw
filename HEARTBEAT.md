# HEARTBEAT.md

# Periodic Autonomy Tasks
# Heartbeat fires every 30 minutes. Use this to check on things proactively.

## Project Status
- Check git status for uncommitted changes
- Verify running services (OpenClaw gateway, dashboard, executor)
- Review recent logs for errors

## Memory Maintenance
- Review recent `memory/YYYY-MM-DD.md` files
- Update `MEMORY.md` with significant learnings from daily notes
- Ensure daily notes are being written

## System Health
- Check disk space in workspace
- Verify critical files exist (AGENTS.md, SOUL.md, USER.md, TOOLS.md)
- Review any pending tasks or reminders

## Trade Monitoring
- Check PolyClaw agent balance and positions (if executor running)
- Monitor recent trades in `data/executions.jsonl`
- Review recommendations from PolyWhale in `data/recommendations.jsonl`
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
- **Review and improve Polymarket skills**: Read `skills/polywhale/SKILL.md`, `skills/polymarket-exec/SKILL.md`, `skills/polyclaw/SKILL.md`
- **Update trading strategies**: Incorporate new learnings from trades, market analysis, and external sources
- **Enhance skill documentation**: Improve SKILL.md files with better examples, clearer instructions, and updated strategies
- **Search ClawHub for new Polymarket skills**: Check if there are better skills available that can be integrated
- **Test and refine**: Run analysis on sample markets, verify strategies work, update code if needed
- **Document improvements**: Write what was learned/improved in `memory/YYYY-MM-DD.md` and update `MEMORY.md` with significant changes

**Action Items:**
1. Read all Polymarket skill files
2. Identify areas for improvement (strategies, code, documentation)
3. Make improvements proactively (update files, add examples, refine logic)
4. Test improvements if possible
5. Document what was done
