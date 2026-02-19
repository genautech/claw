"""
FastAPI Backend for ClawdBot Configuration Dashboard
Deployed to Cloud Run (us-east1)
"""

import os
from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import firebase_admin
from firebase_admin import credentials, firestore
import httpx

# Initialize Firebase Admin SDK
FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "openslaver")

if not firebase_admin._apps:
    # Use default credentials (Cloud Run service account or local gcloud auth)
    cred = credentials.ApplicationDefault()
    firebase_admin.initialize_app(cred, {"projectId": FIREBASE_PROJECT_ID})

db = firestore.client()

app = FastAPI(
    title="ClawdBot Config API",
    description="Backend API for ClawdBot configuration and data persistence",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to specific domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Key authentication (simple for now, can upgrade to Firebase Auth)
API_KEY = os.getenv("API_KEY", "change-me-in-production")


def verify_api_key(x_api_key: Optional[str] = Header(None)) -> bool:
    """Verify API key from header."""
    if not x_api_key or x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return True


# Pydantic Models
class ConfigUpdate(BaseModel):
    gateway: Optional[Dict[str, Any]] = None
    channels: Optional[Dict[str, Any]] = None
    skills: Optional[Dict[str, Any]] = None
    updated_by: Optional[str] = None


class Prediction(BaseModel):
    market_id: str
    market_question: str
    edge: float = Field(..., ge=0, le=1)
    confidence: str = Field(..., pattern="^(HIGH|MEDIUM|LOW)$")
    decision: str
    source: str = "polywhale"
    data_sources: List[str] = []
    timestamp: Optional[datetime] = None


class Trade(BaseModel):
    trade_id: str
    market_id: str
    side: str = Field(..., pattern="^(YES|NO)$")
    size: float = Field(..., gt=0)
    entry_price: float = Field(..., ge=0, le=1)
    exit_price: Optional[float] = None
    status: str = Field(..., pattern="^(open|closed|closing)$")
    pnl: float = 0.0
    timestamp: Optional[datetime] = None


class Metric(BaseModel):
    type: str = Field(..., pattern="^(latency|exposure|win_rate)$")
    value: float
    component: Optional[str] = None
    timestamp: Optional[datetime] = None


# Routes

@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "service": "clawdbot-config-api"}


@app.get("/config")
async def get_config(api_key: bool = Depends(verify_api_key)):
    """Get ClawdBot configuration from Firestore."""
    try:
        doc_ref = db.collection("config").document("main")
        doc = doc_ref.get()
        if doc.exists:
            return {"success": True, "data": doc.to_dict()}
        else:
            return {"success": True, "data": None}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/config")
async def update_config(
    config: ConfigUpdate,
    api_key: bool = Depends(verify_api_key)
):
    """Update ClawdBot configuration in Firestore."""
    try:
        doc_ref = db.collection("config").document("main")
        update_data = config.dict(exclude_none=True)
        update_data["updated_at"] = firestore.SERVER_TIMESTAMP
        
        if not doc_ref.get().exists:
            # Create new document
            doc_ref.set(update_data)
        else:
            # Update existing
            doc_ref.update(update_data)
        
        return {"success": True, "message": "Config updated"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/predictions")
async def create_prediction(
    prediction: Prediction,
    api_key: bool = Depends(verify_api_key)
):
    """Store a new prediction/analysis in Firestore."""
    try:
        if not prediction.timestamp:
            prediction.timestamp = datetime.utcnow()
        
        doc_ref = db.collection("predictions").document()
        doc_ref.set(prediction.dict())
        
        return {
            "success": True,
            "id": doc_ref.id,
            "message": "Prediction stored"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/predictions")
async def get_predictions(
    market_id: Optional[str] = None,
    limit: int = 50,
    api_key: bool = Depends(verify_api_key)
):
    """Get predictions from Firestore."""
    try:
        query = db.collection("predictions").order_by("timestamp", direction=firestore.Query.DESCENDING).limit(limit)
        
        if market_id:
            query = query.where("market_id", "==", market_id)
        
        docs = query.stream()
        predictions = [{"id": doc.id, **doc.to_dict()} for doc in docs]
        
        return {"success": True, "data": predictions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/trades")
async def create_trade(
    trade: Trade,
    api_key: bool = Depends(verify_api_key)
):
    """Store a new trade in Firestore."""
    try:
        if not trade.timestamp:
            trade.timestamp = datetime.utcnow()
        
        doc_ref = db.collection("trades").document()
        doc_ref.set(trade.dict())
        
        return {
            "success": True,
            "id": doc_ref.id,
            "message": "Trade stored"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/trades")
async def get_trades(
    status: Optional[str] = None,
    limit: int = 50,
    api_key: bool = Depends(verify_api_key)
):
    """Get trades from Firestore."""
    try:
        query = db.collection("trades").order_by("timestamp", direction=firestore.Query.DESCENDING).limit(limit)
        
        if status:
            query = query.where("status", "==", status)
        
        docs = query.stream()
        trades = [{"id": doc.id, **doc.to_dict()} for doc in docs]
        
        return {"success": True, "data": trades}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/metrics")
async def create_metric(
    metric: Metric,
    api_key: bool = Depends(verify_api_key)
):
    """Store a new metric in Firestore."""
    try:
        if not metric.timestamp:
            metric.timestamp = datetime.utcnow()
        
        doc_ref = db.collection("metrics").document()
        doc_ref.set(metric.dict())
        
        return {
            "success": True,
            "id": doc_ref.id,
            "message": "Metric stored"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/metrics")
async def get_metrics(
    metric_type: Optional[str] = None,
    limit: int = 100,
    api_key: bool = Depends(verify_api_key)
):
    """Get metrics from Firestore."""
    try:
        query = db.collection("metrics").order_by("timestamp", direction=firestore.Query.DESCENDING).limit(limit)
        
        if metric_type:
            query = query.where("type", "==", metric_type)
        
        docs = query.stream()
        metrics = [{"id": doc.id, **doc.to_dict()} for doc in docs]
        
        return {"success": True, "data": metrics}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/polyclaw/{agent_id}/positions")
async def get_polyclaw_positions(
    agent_id: str,
    api_key: bool = Depends(verify_api_key)
):
    """Proxy to Polyclaw API - get agent positions."""
    polyclaw_api_key = os.getenv("POLYCLAW_AGENT_API_KEY")
    if not polyclaw_api_key:
        raise HTTPException(status_code=500, detail="Polyclaw API key not configured")
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://api.polyclaw.ai/agents/{agent_id}/positions",
                headers={"Authorization": f"Bearer {polyclaw_api_key}"},
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/polyclaw/{agent_id}/trades")
async def get_polyclaw_trades(
    agent_id: str,
    limit: int = 50,
    api_key: bool = Depends(verify_api_key)
):
    """Proxy to Polyclaw API - get agent trades."""
    polyclaw_api_key = os.getenv("POLYCLAW_AGENT_API_KEY")
    if not polyclaw_api_key:
        raise HTTPException(status_code=500, detail="Polyclaw API key not configured")
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://api.polyclaw.ai/agents/{agent_id}/trades",
                headers={"Authorization": f"Bearer {polyclaw_api_key}"},
                params={"limit": limit},
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/polyclaw/{agent_id}/metrics")
async def get_polyclaw_metrics(
    agent_id: str,
    api_key: bool = Depends(verify_api_key)
):
    """Proxy to Polyclaw API - get agent metrics."""
    polyclaw_api_key = os.getenv("POLYCLAW_AGENT_API_KEY")
    if not polyclaw_api_key:
        raise HTTPException(status_code=500, detail="Polyclaw API key not configured")
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://api.polyclaw.ai/agents/{agent_id}/metrics",
                headers={"Authorization": f"Bearer {polyclaw_api_key}"},
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8080")))
