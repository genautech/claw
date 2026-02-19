# ClawdBot - Implementation Guide

## Current Setup

| Component | Status | Details |
|-----------|--------|---------|
| **OpenClaw** | ✅ Running | v2026.2.15, gateway on port 18789 |
| **Model** | ✅ `openai/gpt-4o` | Via OpenAI Codex OAuth |
| **Workspace** | ✅ `/Users/genautech/clawd` | Agent reads SOUL.md, AGENTS.md, etc. |
| **WhatsApp** | ✅ Linked | Auth active |
| **Telegram** | ✅ Connected | @genaubbt_bot |
| **Discord** | ⚠️ Plugin enabled | Bot token not yet configured |
| **Web Chat** | ✅ Available | `http://127.0.0.1:18789/chat` |
| **Monitoring Dashboard** | ✅ Available | `http://127.0.0.1:8787` |
| **Polymarket Executor** | ✅ Running (dry-run) | `http://127.0.0.1:8789` |

## 📁 Project Structure

```
clawd/
├── AGENTS.md               # Agent behavior rules
├── SOUL.md                 # Agent personality
├── USER.md                 # About the human
├── IDENTITY.md             # Agent identity (name, vibe, emoji)
├── HEARTBEAT.md            # Periodic check tasks
├── TOOLS.md                # Local tool notes
├── BOOTSTRAP.md            # First-run onboarding
├── MEMORY.md               # Long-term memory (created after onboard)
├── memory/                 # Daily memory files
├── config/
│   └── openclaw-config.json5   # Config template (mirrors live)
├── scripts/
│   ├── setup.sh                # One-shot setup script
│   └── start-dashboard.sh      # Launch monitoring dashboard
├── dashboard-web/              # Local monitoring dashboard
│   └── index.html              # Single-page dashboard (port 8787)
├── skills/
│   ├── polyclaw/           # Polymarket trading skill
│   ├── polywhale/          # Polymarket analysis skill
│   ├── latencyninja/       # HFT latency optimizer
│   ├── configdash/         # Dashboard config skill
│   └── polymarket-exec/    # Direct Polymarket executor
├── data/                   # Trading data
│   ├── recommendations.jsonl  # PolyWhale recommendations
│   └── executions.jsonl       # Trade execution history
├── dashboard/              # Streamlit dashboard (local)
│   ├── dashboard.py
│   ├── pages/
│   └── requirements.txt
├── firebase/               # Firebase deployment (optional)
│   ├── api/                # FastAPI backend (Cloud Run)
│   ├── web/                # Next.js dashboard (Firebase Hosting)
│   ├── firestore.rules
│   └── firebase.json
├── canvas/                 # Web canvas
│   └── index.html
└── references/             # Reference implementations
    └── polyclaw-chainstack/
```

## 🚀 Quick Start

### 1. Setup (first time)

```bash
cd clawd
bash scripts/setup.sh
```

### 2. Start the gateway

```bash
openclaw gateway restart
openclaw gateway health
```

### 3. Start monitoring dashboard

```bash
bash scripts/start-dashboard.sh
```

Opens: **http://127.0.0.1:8787** (auto-includes gateway token in URL)

### 4. Chat via web

Open: **http://127.0.0.1:18789/chat?session=agent%3Amain%3Amain**

### 5. Chat via TUI

```bash
openclaw onboard    # First time (interactive setup)
openclaw tui        # Subsequent sessions
```

## 🔧 Configuration

### Live Config

Location: `~/.openclaw/openclaw.json`

Key settings:
- **Model:** `openai/gpt-4o` (via OpenAI Codex OAuth)
- **Workspace:** `/Users/genautech/clawd`
- **Gateway:** port 18789, bind auto, token auth
- **Tools:** messaging profile, fs workspaceOnly
- **Plugins:** telegram, whatsapp, discord (all enabled)

### Available API Keys (env)

| Key | Purpose |
|-----|---------|
| `OPENAI_API_KEY` | OpenAI models, image gen, whisper |
| `ANTHROPIC_API_KEY` | Claude models |
| `GOOGLE_API_KEY` | Gemini models |

### Auth Profile

`openai-codex:default` — OAuth-based, linked to ChatGPT Plus account (`genautech`).

### Installed Skills

**Bundled (OpenClaw):**
- clawhub, coding-agent, gemini, github, healthcheck
- nano-banana-pro, openai-image-gen, openai-whisper-api
- session-logs, skill-creator, weather

**Workspace:**
- PolyWhale — Polymarket analyst
- LatencyNinja — HFT latency optimizer

**Configured:**
- polyclaw — Polymarket trading (enabled)
- goplaces — Google Places
- nano-banana-pro — Gemini image gen

## 📱 Channel Setup

### Web Chat (ready)
Just open: `http://127.0.0.1:18789/chat`

### WhatsApp (linked)
Already paired. Messages route through the gateway automatically.

### Telegram (needs bot token)

1. Open Telegram → search `@BotFather`
2. Send `/newbot` → pick name and username
3. Save the bot token
4. Configure:
   ```bash
   openclaw config set channels.telegram.botToken "YOUR_BOT_TOKEN"
   openclaw gateway restart
   ```

### Discord (needs bot token)

1. Go to https://discord.com/developers/applications
2. Create app → Bot → copy token
3. Configure:
   ```bash
   openclaw config set channels.discord.botToken "YOUR_BOT_TOKEN"
   openclaw gateway restart
   ```

## 🧪 Testing

### Test gateway
```bash
openclaw gateway health
```

### Test monitoring dashboard
```bash
bash scripts/start-dashboard.sh
# Open http://127.0.0.1:8787 in browser
```

### Test web chat
Open `http://127.0.0.1:18789/chat?session=agent%3Amain%3Amain` and send a message.

### Test TUI
```bash
openclaw tui
```

## 🔧 Polymarket Direct Executor

The executor allows direct trading on Polymarket without PolyClaw dashboard dependency.

**Start:**
```bash
bash scripts/start-executor.sh
```

**API:** `http://127.0.0.1:8789`

**Configuration:** See `README_exec.md` for full setup instructions.

**Features:**
- Direct CLOB trading via py-clob-client
- Safety checks (max trade size, slippage limits)
- Integration with PolyWhale recommendations
- External agent support via API
- Dry-run mode for testing

## 📊 Monitoring Dashboard

The local dashboard at `http://127.0.0.1:8787` provides real-time monitoring:

- **Gateway Status** - Health, uptime, response time
- **Agent Info** - Model, workspace, session status
- **Channels** - Telegram/WhatsApp/Discord connection state
- **Skills** - Installed skills list
- **Sessions** - Active chat sessions
- **Config Viewer** - Read-only config (secrets redacted)
- **Live Logs** - Real-time gateway log stream via WebSocket

**Start:** `bash scripts/start-dashboard.sh`

The dashboard automatically includes your gateway token in the URL for authentication.

## 🐛 Troubleshooting

**Bot stuck "dillydallying":**
- Check model has valid API key/auth
- Current model `openai/gpt-4o` uses OAuth — run `openclaw onboard` if token expired

**Gateway won't start:**
- Check if already running: `openclaw gateway health`
- Stop existing: `openclaw gateway stop`
- Check logs: `~/.openclaw/logs/gateway.err.log`

**Web chat shows blank page:**
- Gateway must be running on port 18789
- Check: `curl http://127.0.0.1:18789/chat`

**WhatsApp disconnected:**
- Re-pair: `openclaw onboard` → follow QR flow

**"State dir migration skipped" warning:**
- Harmless. OpenClaw detected existing config directory.
