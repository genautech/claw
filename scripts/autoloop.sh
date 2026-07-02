#!/usr/bin/env bash
# ============================================================
# Agência Autônoma — Wrapper legado
# ============================================================
# Redireciona para smart-loop.sh (orquestrador inteligente).
# Mantido para compatibilidade com scripts e docs antigos.
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec bash "$SCRIPT_DIR/smart-loop.sh" "$@"
