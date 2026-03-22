#!/bin/bash
export ENVIRONMENT=prod
export DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/mission_control
export AUTH_MODE=local
export LOCAL_AUTH_TOKEN=28564452b9b917626d3826260fa50fc0648905bb6e4fff85f4904bb248ee43ff
export CORS_ORIGINS=http://localhost:3000
export BASE_URL=http://localhost:8000
export DB_AUTO_MIGRATE=true
cd /Users/genautech/clawd/mc-docker/backend
uv run alembic upgrade head
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
