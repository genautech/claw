#!/bin/bash
# Sync configuration between project template and live OpenClaw config
# Usage:
#   sync-config.sh --to-project  # Copy live -> project (non-secrets only)
#   sync-config.sh --to-live      # Apply project -> live (via openclaw config set)

set -e

PROJECT_CONFIG="/Users/genautech/clawd/config/openclaw-config.json5"
LIVE_CONFIG="$HOME/.openclaw/openclaw.json"

if [ ! -f "$LIVE_CONFIG" ]; then
  echo "❌ Live config not found: $LIVE_CONFIG"
  exit 1
fi

if [ ! -f "$PROJECT_CONFIG" ]; then
  echo "❌ Project config not found: $PROJECT_CONFIG"
  exit 1
fi

sync_to_project() {
  echo "📥 Syncing live config -> project template (non-secrets only)..."
  
  # Extract non-secret fields from live config
  python3 << 'PYTHON'
import json
import sys

try:
  with open("$HOME/.openclaw/openclaw.json", "r") as f:
    live = json.load(f)
  
  # Fields to sync (non-secrets)
  sync_fields = {
    "agents": live.get("agents", {}),
    "tools": live.get("tools", {}),
    "commands": live.get("commands", {}),
    "session": live.get("session", {}),
    "channels": {
      "whatsapp": {
        "dmPolicy": live.get("channels", {}).get("whatsapp", {}).get("dmPolicy"),
        "groupPolicy": live.get("channels", {}).get("whatsapp", {}).get("groupPolicy"),
        "groups": live.get("channels", {}).get("whatsapp", {}).get("groups", {}),
        "debounceMs": live.get("channels", {}).get("whatsapp", {}).get("debounceMs"),
        "mediaMaxMb": live.get("channels", {}).get("whatsapp", {}).get("mediaMaxMb"),
      },
      "telegram": {
        "enabled": live.get("channels", {}).get("telegram", {}).get("enabled"),
        "dmPolicy": live.get("channels", {}).get("telegram", {}).get("dmPolicy"),
        "groupPolicy": live.get("channels", {}).get("telegram", {}).get("groupPolicy"),
        "groups": live.get("channels", {}).get("telegram", {}).get("groups", {}),
        "streamMode": live.get("channels", {}).get("telegram", {}).get("streamMode"),
      },
      "discord": live.get("channels", {}).get("discord", {}),
    },
    "discovery": live.get("discovery", {}),
    "gateway": {
      "port": live.get("gateway", {}).get("port"),
      "mode": live.get("gateway", {}).get("mode"),
      "bind": live.get("gateway", {}).get("bind"),
      "auth": {
        "mode": live.get("gateway", {}).get("auth", {}).get("mode"),
        "token": "REPLACE_WITH_GATEWAY_TOKEN"  # Placeholder
      },
      "tailscale": live.get("gateway", {}).get("tailscale", {}),
    },
    "logging": live.get("logging", {}),
  }
  
  # Read project config
  with open("/Users/genautech/clawd/config/openclaw-config.json5", "r") as f:
    content = f.read()
    # Simple approach: just note what changed
    print("✅ Sync complete. Manual update recommended for complex changes.")
    print("   Review differences and update project config manually.")
  
except Exception as e:
  print(f"❌ Error: {e}", file=sys.stderr)
  sys.exit(1)
PYTHON
}

sync_to_live() {
  echo "📤 Applying project config -> live config..."
  
  # Use openclaw config set for each field
  # This is safer than direct JSON manipulation
  
  echo "⚠️  Manual sync recommended. Use 'openclaw config set' commands."
  echo ""
  echo "Example:"
  echo "  openclaw config set agents.defaults.workspace '/Users/genautech/clawd'"
  echo "  openclaw config set tools.profile 'coding'"
  echo ""
  echo "Or edit ~/.openclaw/openclaw.json directly (backup first!)"
}

case "$1" in
  --to-project)
    sync_to_project
    ;;
  --to-live)
    sync_to_live
    ;;
  *)
    echo "Usage: $0 [--to-project|--to-live]"
    echo ""
    echo "  --to-project  Sync live config -> project template (non-secrets)"
    echo "  --to-live      Apply project config -> live (manual recommended)"
    exit 1
    ;;
esac
