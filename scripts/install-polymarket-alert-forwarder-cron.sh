#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPT="$ROOT/scripts/polymarket-alert-forwarder.sh"
TAG="# CLAWD_POLY_ALERT_FWD"

CURRENT="$(crontab -l 2>/dev/null || true)"
CLEANED="$(printf '%s\n' "$CURRENT" | grep -v "$TAG" || true)"
NEW_LINE="*/5 * * * * $SCRIPT $TAG"

{
  printf '%s\n' "$CLEANED"
  printf '%s\n' "$NEW_LINE"
} | crontab -

echo "Installed alert forwarder cron."
crontab -l | grep "$TAG" || true
