#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HOOK_SCRIPT="$ROOT/scripts/polymarket-hooks.sh"
LOG_FILE="$ROOT/logs/polymarket-hooks.log"
TAG="# CLAWD_POLY_HOOK"

mkdir -p "$ROOT/logs"
touch "$LOG_FILE"

CURRENT="$(crontab -l 2>/dev/null || true)"
CLEANED="$(printf '%s\n' "$CURRENT" | grep -v "$TAG" || true)"

NEW_LINES=$(cat <<EOF
*/10 * * * * $HOOK_SCRIPT health >> $LOG_FILE 2>&1 $TAG health
*/15 * * * * $HOOK_SCRIPT trade >> $LOG_FILE 2>&1 $TAG trade
*/30 * * * * $HOOK_SCRIPT risk >> $LOG_FILE 2>&1 $TAG risk
0 * * * * $HOOK_SCRIPT resolution >> $LOG_FILE 2>&1 $TAG resolution
EOF
)

{
  printf '%s\n' "$CLEANED"
  printf '%s\n' "$NEW_LINES"
} | crontab -

echo "Installed Polymarket hook cron jobs."
crontab -l | grep "$TAG" || true
