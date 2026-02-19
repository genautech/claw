"""
Firestore Sync - Backup and sync data to Firestore
"""

import json
import os
from datetime import datetime
from pathlib import Path
import streamlit as st

try:
    import firebase_admin
    from firebase_admin import credentials, firestore
    FIREBASE_AVAILABLE = True
except ImportError:
    FIREBASE_AVAILABLE = False
    st.error("⚠️ Firebase Admin SDK not installed. Run: `pip install firebase-admin google-cloud-firestore`")

OPENCLAW_DIR = Path.home() / ".openclaw"
CONFIG_FILE = OPENCLAW_DIR / "openclaw.json"

st.title("☁️ Firestore Sync")
st.markdown("Sync ClawdBot data to/from Firestore")

if not FIREBASE_AVAILABLE:
    st.stop()

# Initialize Firebase
FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "openslaver")

if not firebase_admin._apps:
    try:
        # Try to use default credentials (Cloud Run / local with gcloud auth)
        cred = credentials.ApplicationDefault()
        firebase_admin.initialize_app(cred, {"projectId": FIREBASE_PROJECT_ID})
        st.success(f"✅ Firebase initialized — project: **{FIREBASE_PROJECT_ID}**")
    except Exception as e:
        st.warning(f"Could not initialize with default credentials: {e}")
        st.info("💡 For local dev, run: `gcloud auth application-default login`")
        st.stop()

db = firestore.client()

# Sync operations
tab1, tab2, tab3, tab4 = st.tabs(["📤 Upload Config", "📥 Download Config", "📊 Sync Predictions", "📈 Sync Metrics"])

with tab1:
    st.subheader("Upload Config to Firestore")
    
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
            
            st.json(config)
            
            if st.button("Upload Config"):
                try:
                    doc_ref = db.collection("config").document("main")
                    config["updated_at"] = firestore.SERVER_TIMESTAMP
                    config["updated_by"] = "streamlit_dashboard"
                    doc_ref.set(config)
                    st.success("✅ Config uploaded to Firestore!")
                except Exception as e:
                    st.error(f"Error uploading: {e}")
        except Exception as e:
            st.error(f"Error reading config: {e}")
    else:
        st.warning("Config file not found")

with tab2:
    st.subheader("Download Config from Firestore")
    
    if st.button("Download Config"):
        try:
            doc_ref = db.collection("config").document("main")
            doc = doc_ref.get()
            
            if doc.exists:
                config_data = doc.to_dict()
                st.json(config_data)
                
                if st.button("Save to Local Config"):
                    try:
                        with open(CONFIG_FILE, 'w') as f:
                            json.dump(config_data, f, indent=2, default=str)
                        st.success("✅ Config downloaded and saved!")
                    except Exception as e:
                        st.error(f"Error saving: {e}")
            else:
                st.info("No config found in Firestore")
        except Exception as e:
            st.error(f"Error downloading: {e}")

with tab3:
    st.subheader("Sync Predictions")
    
    st.markdown("Upload prediction data from local analysis to Firestore")
    
    # Example: Create a test prediction
    with st.form("prediction_form"):
        market_id = st.text_input("Market ID", value="0x...")
        market_question = st.text_input("Market Question", value="Will BTC > 150k?")
        edge = st.slider("Edge", 0.0, 1.0, 0.12, 0.01)
        confidence = st.selectbox("Confidence", ["HIGH", "MEDIUM", "LOW"])
        decision = st.selectbox("Decision", ["BUY_YES", "BUY_NO", "HEDGE", "PASS"])
        
        submitted = st.form_submit_button("Upload Prediction")
        
        if submitted:
            try:
                prediction_data = {
                    "market_id": market_id,
                    "market_question": market_question,
                    "edge": edge,
                    "confidence": confidence,
                    "decision": decision,
                    "source": "polywhale",
                    "data_sources": ["gamma_api"],
                    "timestamp": firestore.SERVER_TIMESTAMP
                }
                
                doc_ref = db.collection("predictions").document()
                doc_ref.set(prediction_data)
                st.success(f"✅ Prediction uploaded! ID: {doc_ref.id}")
            except Exception as e:
                st.error(f"Error uploading: {e}")
    
    # View recent predictions
    st.markdown("### Recent Predictions")
    if st.button("Load Recent Predictions"):
        try:
            predictions_ref = db.collection("predictions").order_by("timestamp", direction=firestore.Query.DESCENDING).limit(10)
            docs = predictions_ref.stream()
            
            predictions = []
            for doc in docs:
                data = doc.to_dict()
                data["id"] = doc.id
                predictions.append(data)
            
            if predictions:
                st.json(predictions)
            else:
                st.info("No predictions found")
        except Exception as e:
            st.error(f"Error loading: {e}")

with tab4:
    st.subheader("Sync Metrics")
    
    st.markdown("Upload latency and performance metrics to Firestore")
    
    with st.form("metric_form"):
        metric_type = st.selectbox("Metric Type", ["latency", "exposure", "win_rate"])
        metric_value = st.number_input("Value", value=0.0)
        component = st.text_input("Component (optional)", value="")
        
        submitted = st.form_submit_button("Upload Metric")
        
        if submitted:
            try:
                metric_data = {
                    "type": metric_type,
                    "value": metric_value,
                    "component": component if component else None,
                    "timestamp": firestore.SERVER_TIMESTAMP
                }
                
                doc_ref = db.collection("metrics").document()
                doc_ref.set(metric_data)
                st.success(f"✅ Metric uploaded! ID: {doc_ref.id}")
            except Exception as e:
                st.error(f"Error uploading: {e}")
    
    # View recent metrics
    st.markdown("### Recent Metrics")
    metric_type_filter = st.selectbox("Filter by Type", ["all", "latency", "exposure", "win_rate"])
    
    if st.button("Load Recent Metrics"):
        try:
            query = db.collection("metrics").order_by("timestamp", direction=firestore.Query.DESCENDING).limit(20)
            
            if metric_type_filter != "all":
                query = query.where("type", "==", metric_type_filter)
            
            docs = query.stream()
            
            metrics = []
            for doc in docs:
                data = doc.to_dict()
                data["id"] = doc.id
                metrics.append(data)
            
            if metrics:
                st.json(metrics)
            else:
                st.info("No metrics found")
        except Exception as e:
            st.error(f"Error loading: {e}")
