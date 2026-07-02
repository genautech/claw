# TOOLS.md - Local Notes

Skills define *how* tools work. This file is for *your* specifics — the stuff that's unique to your setup.

## Local Services

### Gateway
- **URL:** http://127.0.0.1:18789
- **Web Chat:** http://127.0.0.1:18789/chat?session=agent%3Amain%3Amain
- **Control UI:** http://127.0.0.1:18789 (with token in URL)

### PolyClaw Trading Dashboard (principal)
- **URL:** http://127.0.0.1:3333
- **Start:** `bash scripts/start-dashboard-next.sh`
- **Prod local (perf):** `cd dashboard-next && npm run build && npm run start -- -p 3333`
- **Skill:** `skills/dashboard-next/SKILL.md`

### Clawd Monitoring Dashboard (legado)
- **URL:** http://127.0.0.1:8787
- **With auth:** http://127.0.0.1:8787/#token=(gateway token)
- **Start:** `bash scripts/start-dashboard.sh`

### CorrectionAgent
- **Log:** `/tmp/correctionagent.log`
- **Fila:** `data/approved_corrections.jsonl` → `data/executed_corrections.jsonl`
- **Start:** incluído em `start-dashboard-next.sh` (dedupe automático)

### Polymarket Executor
- **URL:** http://127.0.0.1:8789
- **Health:** http://127.0.0.1:8789/health
- **Mode:** DRY_RUN (testing) — change to live when wallet is configured
- **Start:** `bash scripts/start-executor.sh`

## Channels

### Telegram
- Bot: @genaubbt_bot
- User ID: 7282332454

### WhatsApp
- Number: +554187607512
- Status: linked

### Discord
- Status: not configured (needs bot token)

## Skills

| Skill | Status | Notes |
|-------|--------|-------|
| polyclaw | enabled | Needs operator key from polyclaw.ai |
| polywhale | enabled | Analysis skill — writes to data/recommendations.jsonl |
| latencyninja | enabled | Latency monitoring |
| configdash | enabled | Needs Firebase API key |
| polymarket-exec | enabled | Running on port 8789 (live trading mode) |

## Config Locations
- **Live:** `~/.openclaw/openclaw.json`
- **Template:** `config/openclaw-config.json5`
- **Logs:** `/tmp/openclaw/openclaw-YYYY-MM-DD.log`
- **Gateway logs:** `~/.openclaw/logs/`
- **Executor logs:** `logs/polymarket-exec.log`

---

Add whatever helps you do your job. This is your cheat sheet.
