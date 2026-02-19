# Firebase Setup for ClawdBot Configuration Dashboard

## Project Info

| Field | Value |
|-------|-------|
| **Project ID** | `openslaver` |
| **Auth Domain** | `openslaver.firebaseapp.com` |
| **Storage Bucket** | `openslaver.firebasestorage.app` |
| **App ID** | `1:376161033221:web:d648c15b3c914f6af8d06c` |
| **Measurement ID** | `G-R3GG7M7WLD` |

## Project Structure

- `api/` - FastAPI backend for Cloud Run
- `web/` - Next.js dashboard for Firebase Hosting
- `functions/` - Cloud Functions (if needed)

## Architecture

```
Browser (Next.js)
  ├── Firestore Direct (reads) ← firebase/web/lib/firestore.ts
  └── Cloud Run API (writes)   ← firebase/web/lib/api.ts
                                    ↓
                              firebase/api/main.py
                                    ↓
                              Firestore (openslaver)
```

**Reads:** The web dashboard reads directly from Firestore using the client SDK (no backend round-trip needed for public collections like predictions, trades, metrics).

**Writes:** All writes go through the Cloud Run API (`api/main.py`) which uses Firebase Admin SDK for server-side auth and validation.

## Firestore Collections Schema

### `config/` - ClawdBot Configuration
Stores encrypted ClawdBot settings (gateway, channels, skills, API keys).

```json
{
  "id": "main",
  "gateway": { "mode": "local", "port": 18789 },
  "channels": { "telegram": { "botToken": "encrypted" } },
  "skills": { "polyclaw": { "enabled": true } },
  "updated_at": "2026-02-XX",
  "updated_by": "user_id"
}
```

### `predictions/` - Market Analyses
Historical prediction data, edge calculations, signal history.

```json
{
  "id": "auto-generated",
  "market_id": "0x...",
  "market_question": "Will BTC > 150k?",
  "edge": 0.12,
  "confidence": "HIGH",
  "decision": "BUY_YES",
  "timestamp": "2026-02-XX",
  "source": "polywhale",
  "data_sources": ["gamma_api", "kalshi"]
}
```

### `trades/` - Executed Trades
Trade execution logs, PnL, resolution data.

```json
{
  "id": "auto-generated",
  "trade_id": "uuid",
  "market_id": "0x...",
  "side": "YES",
  "size": 50,
  "entry_price": 0.65,
  "exit_price": null,
  "status": "open",
  "pnl": 0,
  "timestamp": "2026-02-XX"
}
```

### `metrics/` - Performance Metrics
Latency snapshots, win rate, exposure tracking.

```json
{
  "id": "auto-generated",
  "type": "latency|exposure|win_rate",
  "value": 2400,
  "component": "RPC Call|LLM Response|CLOB Order",
  "timestamp": "2026-02-XX"
}
```

### `cache/` - TTL Cache (Redis Alternative)
Temporary cache documents with TTL for market data, LLM responses.

## Quick Start

### 1. Install Firebase CLI

```bash
npm install -g firebase-tools
```

### 2. Login to Firebase

```bash
firebase login
```

### 3. Set up local auth for Python (backend/Streamlit)

```bash
gcloud auth application-default login
```

### 4. Deploy Firestore rules

```bash
cd firebase
firebase deploy --only firestore:rules
firebase deploy --only firestore:indexes
```

### 5. Run the web dashboard locally

```bash
cd firebase/web
npm install
npm run dev
```

### 6. Deploy to Firebase Hosting

```bash
cd firebase/web
npm run build
cd ..
firebase deploy --only hosting
```

### 7. Deploy API to Cloud Run

```bash
cd firebase/api
bash deploy.sh
```

## Region Configuration

- **Firestore**: us-east1 (closest to Polymarket/Polygon infra)
- **Cloud Run**: us-east1 (same region for low latency)
- **Hosting**: Global CDN (us-east1 primary)

## Security Notes

- API keys stored in `config/` are encrypted at rest
- Firestore rules require authentication for writes
- Public read access for dashboard data (predictions, trades, metrics)
- Config collection requires full auth for read/write
- Firebase web config (apiKey, etc.) is safe to expose — it only identifies the project
