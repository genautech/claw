#!/usr/bin/env bash
# ============================================================
# PolymarketClawBot - One-Shot Setup Script
# ============================================================
# Usage: bash scripts/setup.sh
#
# Prerequisites:
#   - Node.js >= 22
#   - Python 3.11+ with uv
#   - OpenClaw installed (curl -fsSL https://openclaw.ai/install.sh | bash)
#   - .env file with API keys (cp .env.template .env && edit)
# ============================================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${GREEN}[SETUP]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
err()  { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# --- 1. Check prerequisites ---
log "Checking prerequisites..."

node_ver=$(node --version 2>/dev/null || echo "none")
if [[ "$node_ver" == "none" ]]; then
  err "Node.js not found. Install >= 22 from https://nodejs.org"
fi
log "Node.js: $node_ver"

python_ver=$(python3 --version 2>/dev/null || echo "none")
if [[ "$python_ver" == "none" ]]; then
  err "Python3 not found. Install >= 3.11"
fi
log "Python: $python_ver"

if ! command -v uv &>/dev/null; then
  warn "uv not found. Installing..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi
log "uv: $(uv --version 2>/dev/null)"

if ! command -v openclaw &>/dev/null; then
  err "OpenClaw not found. Run: curl -fsSL https://openclaw.ai/install.sh | bash"
fi
log "OpenClaw: $(openclaw --version 2>/dev/null)"

# --- 2. Load .env if exists ---
if [[ -f "$PROJECT_DIR/.env" ]]; then
  log "Loading .env..."
  set -a
  source "$PROJECT_DIR/.env"
  set +a
else
  warn ".env not found. Copy .env.template to .env and fill in your keys."
  warn "  cp $PROJECT_DIR/.env.template $PROJECT_DIR/.env"
fi

# --- 3. Generate gateway token if not set ---
if [[ -z "${OPENCLAW_GATEWAY_TOKEN:-}" ]]; then
  OPENCLAW_GATEWAY_TOKEN=$(openssl rand -hex 32)
  log "Generated gateway token: ${OPENCLAW_GATEWAY_TOKEN:0:8}..."
  warn "Save this token in your .env file!"
fi

# --- 4. Create OpenClaw config ---
log "Creating hardened OpenClaw config..."
mkdir -p ~/.openclaw

cat > ~/.openclaw/openclaw.json << CONFIGEOF
{
  "gateway": {
    "mode": "local",
    "bind": "loopback",
    "port": ${OPENCLAW_GATEWAY_PORT:-18789},
    "auth": {
      "mode": "token",
      "token": "$OPENCLAW_GATEWAY_TOKEN"
    }
  },
  "discovery": {
    "mdns": { "mode": "minimal" }
  },
  "session": {
    "dmScope": "per-channel-peer"
  },
  "agent": {
    "model": "deepseek/deepseek-chat"
  },
  "tools": {
    "profile": "messaging",
    "deny": [
      "group:automation",
      "group:runtime",
      "group:fs",
      "sessions_spawn",
      "sessions_send",
      "gateway",
      "cron"
    ],
    "fs": { "workspaceOnly": true },
    "exec": { "security": "deny", "ask": "always" },
    "elevated": { "enabled": false }
  },
  "channels": {
    "whatsapp": {
      "dmPolicy": "pairing",
      "groups": { "*": { "requireMention": true } }
    },
    "telegram": {
      "dmPolicy": "pairing",
      "groups": { "*": { "requireMention": true } }
    },
    "discord": {
      "dmPolicy": "pairing"
    }
  },
  "logging": {
    "redactSensitive": "tools"
  },
  "skills": {
    "entries": {
      "polyclaw": {
        "enabled": true,
        "env": {
          "CHAINSTACK_NODE": "${CHAINSTACK_NODE:-}",
          "POLYCLAW_PRIVATE_KEY": "${POLYCLAW_PRIVATE_KEY:-}",
          "OPENROUTER_API_KEY": "${OPENROUTER_API_KEY:-}"
        }
      }
    }
  }
}
CONFIGEOF

# --- 5. Lock file permissions ---
log "Setting secure permissions..."
chmod 700 ~/.openclaw
chmod 600 ~/.openclaw/openclaw.json

# --- 6. Install PolyClaw skill ---
log "Installing PolyClaw skill..."
if command -v clawhub &>/dev/null; then
  clawhub install polyclaw 2>/dev/null || warn "clawhub install failed — try manual install"
fi

if [[ -d ~/.openclaw/skills/polyclaw ]]; then
  cd ~/.openclaw/skills/polyclaw
  uv sync 2>/dev/null || pip install -r requirements.txt 2>/dev/null || warn "PolyClaw deps install failed"
  log "PolyClaw skill ready"
else
  warn "PolyClaw skill not found at ~/.openclaw/skills/polyclaw"
  warn "Install manually: clawhub install polyclaw"
fi

# --- 7. Copy custom skills ---
log "Installing custom skills..."
if [[ -d "$PROJECT_DIR/skills/polywhale" ]]; then
  mkdir -p ~/.openclaw/workspace/skills/polywhale
  cp "$PROJECT_DIR/skills/polywhale/SKILL.md" ~/.openclaw/workspace/skills/polywhale/
  log "PolyWhale skill installed"
fi
if [[ -d "$PROJECT_DIR/skills/latencyninja" ]]; then
  mkdir -p ~/.openclaw/workspace/skills/latencyninja
  cp "$PROJECT_DIR/skills/latencyninja/SKILL.md" ~/.openclaw/workspace/skills/latencyninja/
  log "LatencyNinja skill installed"
fi

# --- 8. Install dashboard dependencies ---
log "Installing dashboard dependencies..."
cd "$PROJECT_DIR/dashboard"
pip install -r requirements.txt 2>/dev/null || uv pip install -r requirements.txt 2>/dev/null || warn "Dashboard deps failed"

# --- 9. Security audit ---
log "Running security audit..."
cd "$PROJECT_DIR"
openclaw security audit 2>/dev/null || warn "Security audit had warnings — review output above"

# --- 10. Summary ---
echo ""
echo "============================================================"
log "Setup complete!"
echo "============================================================"
echo ""
echo "  Gateway port:   ${OPENCLAW_GATEWAY_PORT:-18789}"
echo "  Dashboard port:  ${STREAMLIT_PORT:-8501}"
echo "  Config:          ~/.openclaw/openclaw.json"
echo "  Skills:          ~/.openclaw/skills/ + ~/.openclaw/workspace/skills/"
echo ""
echo "  Next steps:"
echo "    1. Start gateway:    openclaw gateway"
echo "    2. Health check:     openclaw gateway health"
echo "    3. Security audit:   openclaw security audit --deep"
echo "    4. Start dashboard:  cd dashboard && streamlit run dashboard.py"
echo "    5. Test PolyClaw:    (via Telegram/Discord) 'What's trending on Polymarket?'"
echo ""
