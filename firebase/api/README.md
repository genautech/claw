# ClawdBot Config API

FastAPI backend deployed to Cloud Run (us-east1) for ClawdBot configuration and data persistence.

## Endpoints

### Config
- `GET /config` - Get ClawdBot configuration
- `PUT /config` - Update ClawdBot configuration

### Predictions
- `POST /predictions` - Store new prediction/analysis
- `GET /predictions?market_id=...&limit=50` - Get predictions

### Trades
- `POST /trades` - Store new trade
- `GET /trades?status=open&limit=50` - Get trades

### Metrics
- `POST /metrics` - Store new metric
- `GET /metrics?metric_type=latency&limit=100` - Get metrics

### Polyclaw Proxy
- `GET /polyclaw/{agent_id}/positions` - Get agent positions
- `GET /polyclaw/{agent_id}/trades` - Get agent trades
- `GET /polyclaw/{agent_id}/metrics` - Get agent metrics

## Authentication

All endpoints require `X-API-Key` header with the API key set in environment variable `API_KEY`.

## Local Development

```bash
cd firebase/api
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your keys
uvicorn main:app --reload
```

## Deploy to Cloud Run

```bash
# Build and deploy
gcloud builds submit --tag gcr.io/PROJECT_ID/clawdbot-api
gcloud run deploy clawdbot-api \
  --image gcr.io/PROJECT_ID/clawdbot-api \
  --platform managed \
  --region us-east1 \
  --allow-unauthenticated \
  --set-env-vars API_KEY=your-secret-key,POLYCLAW_AGENT_API_KEY=pc_agent_...
```

## Environment Variables

- `API_KEY` - API key for authentication (required)
- `POLYCLAW_AGENT_API_KEY` - Polyclaw agent API key (optional, for proxy endpoints)
- `PORT` - Port to listen on (default: 8080, Cloud Run sets this automatically)
