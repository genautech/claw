#!/usr/bin/env bash
# ============================================================
# ClawdBot - Setup Script
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

# --- 4. Configure OpenClaw via CLI (preserves existing config) ---
log "Configuring OpenClaw..."
mkdir -p ~/.openclaw

# Model & workspace
openclaw config set agents.defaults.model.primary "openai/gpt-4o" 2>/dev/null || warn "Could not set model"
openclaw config set agents.defaults.workspace "$PROJECT_DIR" 2>/dev/null || warn "Could not set workspace"

# Gateway
openclaw config set gateway.mode "local" 2>/dev/null || true
openclaw config set gateway.bind "auto" 2>/dev/null || true
openclaw config set gateway.port ${OPENCLAW_GATEWAY_PORT:-18789} 2>/dev/null || true
openclaw config set gateway.auth.mode "token" 2>/dev/null || true
openclaw config set gateway.auth.token "$OPENCLAW_GATEWAY_TOKEN" 2>/dev/null || true

# Tools (agent-friendly defaults)
openclaw config set tools.profile "coding" 2>/dev/null || true
openclaw config set tools.elevated.enabled true 2>/dev/null || true
openclaw config set tools.exec.security "full" 2>/dev/null || true
openclaw config set tools.exec.ask "on-miss" 2>/dev/null || true
openclaw config set tools.fs.workspaceOnly true 2>/dev/null || true

# Channels
openclaw config set channels.whatsapp.dmPolicy "pairing" 2>/dev/null || true
openclaw config set channels.whatsapp.groupPolicy "allowlist" 2>/dev/null || true
openclaw config set channels.whatsapp.debounceMs 0 2>/dev/null || true
openclaw config set channels.whatsapp.mediaMaxMb 50 2>/dev/null || true
openclaw config set channels.telegram.dmPolicy "pairing" 2>/dev/null || true
openclaw config set channels.telegram.groupPolicy "allowlist" 2>/dev/null || true
openclaw config set channels.telegram.streamMode "partial" 2>/dev/null || true
openclaw config set channels.discord.groupPolicy "allowlist" 2>/dev/null || true
openclaw config set channels.discord.dmPolicy "pairing" 2>/dev/null || true

# Plugins
openclaw config set plugins.entries.telegram.enabled true 2>/dev/null || true
openclaw config set plugins.entries.whatsapp.enabled true 2>/dev/null || true
openclaw config set plugins.entries.discord.enabled true 2>/dev/null || true

# Skills
openclaw config set skills.install.nodeManager "npm" 2>/dev/null || true
openclaw config set skills.entries.polyclaw.enabled true 2>/dev/null || true

# Logging
openclaw config set logging.redactSensitive "tools" 2>/dev/null || true

log "Config updated at ~/.openclaw/openclaw.json"

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

# --- 7. Copy custom skills to workspace ---
log "Installing custom skills..."

# Use the project workspace (agents.defaults.workspace)
WORKSPACE_SKILLS="$PROJECT_DIR/skills"
OPENCLAW_WORKSPACE_SKILLS="$HOME/.openclaw/workspace/skills"

if [[ -d "$WORKSPACE_SKILLS/polywhale" ]]; then
  mkdir -p "$OPENCLAW_WORKSPACE_SKILLS/polywhale"
  cp "$WORKSPACE_SKILLS/polywhale/SKILL.md" "$OPENCLAW_WORKSPACE_SKILLS/polywhale/"
  log "PolyWhale skill installed"
fi
if [[ -d "$WORKSPACE_SKILLS/latencyninja" ]]; then
  mkdir -p "$OPENCLAW_WORKSPACE_SKILLS/latencyninja"
  cp "$WORKSPACE_SKILLS/latencyninja/SKILL.md" "$OPENCLAW_WORKSPACE_SKILLS/latencyninja/"
  log "LatencyNinja skill installed"
fi

# --- 8. Install dashboard dependencies ---
if [[ -d "$PROJECT_DIR/dashboard" ]]; then
  log "Installing dashboard dependencies..."
  cd "$PROJECT_DIR/dashboard"
  pip install -r requirements.txt 2>/dev/null || uv pip install -r requirements.txt 2>/dev/null || warn "Dashboard deps failed"
fi

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
echo "  Model:           openai/gpt-4o"
echo "  Workspace:       $PROJECT_DIR"
echo "  Gateway port:    ${OPENCLAW_GATEWAY_PORT:-18789}"
echo "  Config:          ~/.openclaw/openclaw.json"
echo "  Skills:          ~/.openclaw/skills/ + ~/.openclaw/workspace/skills/"
echo ""
echo "  Auth profile:    openai-codex (OAuth)"
echo "  Plugins:         telegram, whatsapp, discord"
echo ""
echo "  Next steps:"
echo "    1. Start gateway:    openclaw gateway restart"
echo "    2. Health check:     openclaw gateway health"
echo "    3. Web chat:         http://127.0.0.1:${OPENCLAW_GATEWAY_PORT:-18789}/chat"
echo "    4. Onboard:          openclaw onboard"
echo "    5. Security audit:   openclaw security audit --deep"
echo ""
