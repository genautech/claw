"""
PolymarketClawBot Dashboard - Main Entry Point
===================================================
Run: streamlit run dashboard.py
URL: http://localhost:8501

Multi-page dashboard with:
- Real-time monitoring (Dashboard)
- Config Editor
- Keys Manager
- Firestore Sync
- Hosting Advisor
"""

import json
from pathlib import Path
import streamlit as st

# --- Config ---
OPENCLAW_DIR = Path.home() / ".openclaw"
GATEWAY_CONFIG = OPENCLAW_DIR / "openclaw.json"

# --- Page Config ---
st.set_page_config(
    page_title="PolymarketClawBot Dashboard",
    page_icon="🦞",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Custom CSS ---
st.markdown("""
<style>
    .stMetric {
        background: rgba(255,255,255,0.05);
        border: 1px solid rgba(255,255,255,0.1);
        border-radius: 12px;
        padding: 12px;
    }
    .risk-alert {
        background: #ff4444;
        color: white;
        padding: 10px 16px;
        border-radius: 8px;
        font-weight: bold;
        margin: 8px 0;
    }
    .safe-indicator {
        background: #00c853;
        color: white;
        padding: 10px 16px;
        border-radius: 8px;
        font-weight: bold;
        margin: 8px 0;
    }
</style>
""", unsafe_allow_html=True)

# --- Sidebar ---
with st.sidebar:
    st.title("🦞 ClawBot Control")
    st.divider()

    # Status indicators
    st.markdown("**System Status**")

    if GATEWAY_CONFIG.exists():
        st.success("OpenClaw Config: Found")
        try:
            with open(GATEWAY_CONFIG) as f:
                config = json.loads(f.read())
            mode = config.get('gateway', {}).get('mode', 'unknown')
            port = config.get('gateway', {}).get('port', 18789)
            st.info(f"Gateway: {mode} (:{port})")
        except Exception:
            st.warning("Config: Parse error")
    else:
        st.error("OpenClaw Config: Not found")

    st.divider()
    st.markdown("**Capital Framework**")
    st.markdown("- Max SB Exposure: **20%**")
    st.markdown("- Max Per Market: **5%**")
    st.markdown("- Stop Loss: **-30%**")
    st.markdown("- Take Profit: **+40%**")
    st.markdown("- Latency Limit: **3000ms**")

# Main content is handled by Streamlit's multi-page system
# Pages are in the pages/ directory
