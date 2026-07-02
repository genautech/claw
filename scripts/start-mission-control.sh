#!/usr/bin/env bash
# Start Mission Control stack (Docker Compose)

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MC_DIR="$ROOT/mission-control"
ENV_FILE="$MC_DIR/myenv.txt"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker não encontrado. Instale Docker Desktop."
  exit 1
fi

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Arquivo de env não encontrado: $ENV_FILE"
  exit 1
fi

cd "$MC_DIR"
echo "Starting Mission Control..."
docker compose -f compose.yml --env-file myenv.txt up -d --build

echo ""
echo "Mission Control URLs:"
echo "  Frontend: http://localhost:3001"
echo "  API docs: http://localhost:8000/docs"
echo ""
docker compose -f compose.yml --env-file myenv.txt ps
