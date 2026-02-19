# Clawd System Skill

This skill teaches agents how to navigate and manage the clawd project structure, sync configurations, and monitor system health.

## Project Structure

The clawd project is the single source of truth. The OpenClaw workspace is symlinked to `/Users/genautech/clawd`, so all files are directly accessible.

### Key Directories

- `skills/` - All OpenClaw skills (including this one)
- `config/` - Configuration templates (`openclaw-config.json5`)
- `memory/` - Daily memory files (`YYYY-MM-DD.md`) and `MEMORY.md`
- `dashboard-web/` - Local monitoring dashboard
- `scripts/` - Utility scripts (sync, start, etc.)
- `data/` - Trade data, recommendations, executions
- `canvas/` - Interactive canvas UI

### Key Files

- `AGENTS.md` - Agent behavior and memory guidelines
- `SOUL.md` - Agent identity and personality
- `USER.md` - User context and preferences
- `TOOLS.md` - Local tool configurations
- `HEARTBEAT.md` - Periodic autonomy tasks
- `MEMORY.md` - Long-term curated memory

## Configuration Management

### Sync Config Between Project and Live

The project config template is at `config/openclaw-config.json5`. The live config is at `~/.openclaw/openclaw.json`.

**To sync from live to project:**
```bash
bash scripts/sync-config.sh --to-project
```

**To sync from project to live:**
```bash
bash scripts/sync-config.sh --to-live
```

**Manual sync via OpenClaw CLI:**
- Read live: `openclaw config get <path>`
- Set live: `openclaw config set <path> <value>`

### Important Config Paths

- `agents.defaults.workspace` - Should be `/Users/genautech/clawd`
- `tools.profile` - Should be `"coding"` for full access
- `tools.deny` - Should NOT include `group:fs` or `group:automation`
- `tools.exec.security` - Should be `"allowlist"` or `"full"` with `ask: "always"`
- `tools.elevated.enabled` - Should be `true`

## Memory Management

### Daily Notes
- Location: `memory/YYYY-MM-DD.md`
- Purpose: Raw logs of daily activity
- Created automatically by agents during work

### Long-term Memory
- Location: `MEMORY.md`
- Purpose: Curated significant events, decisions, learnings
- Updated during heartbeats and compaction cycles
- Only loaded in main sessions (not shared contexts)

### Memory Maintenance Tasks
1. Review recent daily notes
2. Extract significant learnings
3. Update MEMORY.md with distilled insights
4. Clean up outdated information

## System Monitoring

### Gateway Status
- Check: `openclaw health`
- Web UI: `http://127.0.0.1:18789/`
- Dashboard: `http://127.0.0.1:8787`

### Services to Monitor
- OpenClaw Gateway (port 18789)
- Dashboard web server (port 8787)
- Polymarket Executor (port 8789, if running)

### Health Checks
```bash
# Gateway health
openclaw health

# Channel status
openclaw channels status

# Check running processes
ps aux | grep -E "(openclaw|python.*polymarket-exec|python.*http.server)"
```

## Trade Monitoring

### Polymarket Executor
- API: `http://127.0.0.1:8789`
- Health: `GET /health`
- Balance: `GET /balance`
- Positions: `GET /positions`
- Recommendations: `data/recommendations.jsonl`
- Executions: `data/executions.jsonl`

### PolyClaw Integration
- Check agent balance and positions
- Monitor recent trades
- Review recommendations from PolyWhale skill

## Self-Improvement

Agents can modify the project to improve it:

1. **Update Skills**: Edit `skills/*/SKILL.md` files
2. **Fix Bugs**: Modify code in `scripts/`, `dashboard-web/`, etc.
3. **Improve Config**: Update `config/openclaw-config.json5` and sync
4. **Enhance Memory**: Update `MEMORY.md` and daily notes
5. **Add Features**: Create new scripts, skills, or dashboard panels

### Polymarket Training Improvements (PRIORITY)

**You are explicitly tasked with proactively improving Polymarket training.** Read `POLYMARKET_IMPROVEMENTS.md` for detailed instructions.

**What to do:**
- Review and enhance `skills/polywhale/SKILL.md`, `skills/polymarket-exec/SKILL.md`, `skills/polyclaw/SKILL.md`
- Add better examples, clearer strategies, more detailed instructions
- Research and incorporate new trading strategies
- Improve code quality in executor and related scripts
- Test and refine strategies
- Document all improvements

**When to do it:**
- During heartbeats (every 30 minutes)
- During any Polymarket-related session
- Proactively - don't wait to be asked
- Whenever you see something that can be better

**How to do it:**
- Read the skill files
- Identify areas for improvement
- Make the improvements (edit files, add examples, update strategies)
- Test if possible
- Document what you did in `memory/YYYY-MM-DD.md`

### Safety Guidelines
- Always test changes before committing
- Keep backups of important files
- Document changes in memory files
- Ask for approval on destructive operations
- **BUT**: Improving skills and documentation is safe - do it proactively

## Common Tasks

### Start Full Environment
```bash
bash scripts/start.sh
```

This launches:
- Gateway (if not running)
- Dashboard web server
- Prints all access URLs

### Sync Configuration
```bash
bash scripts/sync-config.sh --to-project  # Live -> Project
bash scripts/sync-config.sh --to-live     # Project -> Live
```

### Check System Status
```bash
openclaw health
openclaw channels status
bash scripts/ensure-running.sh
```

## Reporting Status

When reporting system status to users, include:
- Gateway health (online/offline)
- Active channels (Telegram, WhatsApp, etc.)
- Active sessions count
- Recent memory updates
- Trade activity (if applicable)
- Any errors or warnings
