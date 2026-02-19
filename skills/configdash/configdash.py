#!/usr/bin/env python3
"""
ConfigDash - ClawdBot configuration and data management via Firestore
"""

import os
import json
import httpx
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

API_BASE_URL = os.getenv("API_BASE_URL", "https://clawdbot-api-xxxxx-uc.a.run.app")
API_KEY = os.getenv("FIREBASE_API_KEY", "")
OPENCLAW_CONFIG = Path.home() / ".openclaw" / "openclaw.json"

HEADERS = {
    "Content-Type": "application/json",
    "X-API-Key": API_KEY,
}


class ConfigDash:
    """ClawdBot configuration and data management."""

    def __init__(self):
        if not API_KEY:
            raise ValueError("FIREBASE_API_KEY not set in environment")

    def get_config(self) -> Optional[Dict[str, Any]]:
        """Get ClawdBot configuration from Firestore."""
        try:
            response = httpx.get(f"{API_BASE_URL}/config", headers=HEADERS, timeout=10.0)
            response.raise_for_status()
            data = response.json()
            return data.get("data") if data.get("success") else None
        except Exception as e:
            print(f"Error getting config: {e}")
            return None

    def update_config(self, config_updates: Dict[str, Any]) -> bool:
        """Update ClawdBot configuration in Firestore."""
        try:
            response = httpx.put(
                f"{API_BASE_URL}/config",
                headers=HEADERS,
                json=config_updates,
                timeout=10.0
            )
            response.raise_for_status()
            data = response.json()
            return data.get("success", False)
        except Exception as e:
            print(f"Error updating config: {e}")
            return False

    def sync_config_to_local(self) -> bool:
        """Download config from Firestore and save to local file."""
        config = self.get_config()
        if not config:
            return False

        try:
            # Remove Firestore-specific fields
            config.pop("updated_at", None)
            config.pop("updated_by", None)

            with open(OPENCLAW_CONFIG, 'w') as f:
                json.dump(config, f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving config: {e}")
            return False

    def sync_config_to_firestore(self) -> bool:
        """Upload local config to Firestore."""
        if not OPENCLAW_CONFIG.exists():
            return False

        try:
            with open(OPENCLAW_CONFIG, 'r') as f:
                config = json.load(f)

            return self.update_config(config)
        except Exception as e:
            print(f"Error syncing config: {e}")
            return False

    def store_prediction(
        self,
        market_id: str,
        market_question: str,
        edge: float,
        confidence: str,
        decision: str,
        source: str = "polywhale",
        data_sources: Optional[List[str]] = None
    ) -> Optional[str]:
        """Store a prediction/analysis in Firestore."""
        prediction = {
            "market_id": market_id,
            "market_question": market_question,
            "edge": edge,
            "confidence": confidence,
            "decision": decision,
            "source": source,
            "data_sources": data_sources or [],
            "timestamp": datetime.utcnow().isoformat()
        }

        try:
            response = httpx.post(
                f"{API_BASE_URL}/predictions",
                headers=HEADERS,
                json=prediction,
                timeout=10.0
            )
            response.raise_for_status()
            data = response.json()
            return data.get("id") if data.get("success") else None
        except Exception as e:
            print(f"Error storing prediction: {e}")
            return None

    def get_predictions(
        self,
        market_id: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get predictions from Firestore."""
        params = {"limit": limit}
        if market_id:
            params["market_id"] = market_id

        try:
            response = httpx.get(
                f"{API_BASE_URL}/predictions",
                headers=HEADERS,
                params=params,
                timeout=10.0
            )
            response.raise_for_status()
            data = response.json()
            return data.get("data", []) if data.get("success") else []
        except Exception as e:
            print(f"Error getting predictions: {e}")
            return []

    def store_metric(
        self,
        metric_type: str,
        value: float,
        component: Optional[str] = None
    ) -> Optional[str]:
        """Store a metric in Firestore."""
        metric = {
            "type": metric_type,
            "value": value,
            "component": component,
            "timestamp": datetime.utcnow().isoformat()
        }

        try:
            response = httpx.post(
                f"{API_BASE_URL}/metrics",
                headers=HEADERS,
                json=metric,
                timeout=10.0
            )
            response.raise_for_status()
            data = response.json()
            return data.get("id") if data.get("success") else None
        except Exception as e:
            print(f"Error storing metric: {e}")
            return None

    def store_trade(
        self,
        trade_id: str,
        market_id: str,
        side: str,
        size: float,
        entry_price: float,
        status: str = "open",
        pnl: float = 0.0
    ) -> Optional[str]:
        """Store a trade in Firestore."""
        trade = {
            "trade_id": trade_id,
            "market_id": market_id,
            "side": side,
            "size": size,
            "entry_price": entry_price,
            "status": status,
            "pnl": pnl,
            "timestamp": datetime.utcnow().isoformat()
        }

        try:
            response = httpx.post(
                f"{API_BASE_URL}/trades",
                headers=HEADERS,
                json=trade,
                timeout=10.0
            )
            response.raise_for_status()
            data = response.json()
            return data.get("id") if data.get("success") else None
        except Exception as e:
            print(f"Error storing trade: {e}")
            return None


# Singleton instance
_configdash: Optional[ConfigDash] = None


def get_configdash() -> ConfigDash:
    """Get ConfigDash singleton instance."""
    global _configdash
    if _configdash is None:
        _configdash = ConfigDash()
    return _configdash


if __name__ == "__main__":
    # CLI usage example
    import sys

    if len(sys.argv) < 2:
        print("Usage: configdash.py <command> [args...]")
        print("Commands: get-config, sync-to-local, sync-to-firestore, store-prediction")
        sys.exit(1)

    cmd = sys.argv[1]
    dash = get_configdash()

    if cmd == "get-config":
        config = dash.get_config()
        print(json.dumps(config, indent=2) if config else "No config found")

    elif cmd == "sync-to-local":
        if dash.sync_config_to_local():
            print("✅ Config synced to local")
        else:
            print("❌ Failed to sync config")

    elif cmd == "sync-to-firestore":
        if dash.sync_config_to_firestore():
            print("✅ Config synced to Firestore")
        else:
            print("❌ Failed to sync config")

    elif cmd == "store-prediction":
        if len(sys.argv) < 7:
            print("Usage: store-prediction <market_id> <question> <edge> <confidence> <decision>")
            sys.exit(1)
        pred_id = dash.store_prediction(
            sys.argv[2], sys.argv[3], float(sys.argv[4]), sys.argv[5], sys.argv[6]
        )
        print(f"✅ Prediction stored: {pred_id}" if pred_id else "❌ Failed to store prediction")
