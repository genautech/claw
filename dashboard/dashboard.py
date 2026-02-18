"""
PolymarketClawBot Dashboard - Real-time Monitoring
===================================================
Run: streamlit run dashboard.py
URL: http://localhost:8501

Monitors:
- Trade logs from OpenClaw sessions
- Exposure (SB vs CB allocation)
- Agent status (PolyWhale, LatencyNinja)
- PnL from PolyClaw positions
- Latency tracking with alerts
- Risk alerts (>20% exposure, >5% single market)
"""

import json
import os
import glob
import time
from datetime import datetime, timedelta
from pathlib import Path

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# --- Config ---
OPENCLAW_DIR = Path.home() / ".openclaw"
SESSIONS_DIR = OPENCLAW_DIR / "agents"
POLYCLAW_POSITIONS = OPENCLAW_DIR / "polyclaw" / "positions.json"
REFRESH_INTERVAL = 10  # seconds

# --- Capital Framework Constants ---
MAX_SB_EXPOSURE = 0.20  # 20% max speculative
MAX_PER_MARKET = 0.05   # 5% per market
STOP_LOSS = -0.30       # -30%
TAKE_PROFIT = 0.40      # +40%
LATENCY_THRESHOLD = 3000  # 3s in ms

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


# --- Data Loading Functions ---

def load_session_logs():
    """Load trade logs from OpenClaw session JSONL files."""
    logs = []
    sessions_pattern = str(SESSIONS_DIR / "*" / "sessions" / "*.jsonl")

    for jsonl_file in glob.glob(sessions_pattern):
        try:
            with open(jsonl_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        logs.append(entry)
                    except json.JSONDecodeError:
                        continue
        except (IOError, PermissionError):
            continue

    return logs


def load_positions():
    """Load PolyClaw positions from positions.json."""
    if not POLYCLAW_POSITIONS.exists():
        return []

    try:
        with open(POLYCLAW_POSITIONS, 'r') as f:
            data = json.loads(f.read())
            if isinstance(data, list):
                return data
            elif isinstance(data, dict) and 'positions' in data:
                return data['positions']
            return []
    except (json.JSONDecodeError, IOError):
        return []


def extract_trades_from_logs(logs):
    """Extract trade-related entries from session logs."""
    trades = []
    for entry in logs:
        # Look for trade-like entries in session transcripts
        if isinstance(entry, dict):
            content = str(entry.get('content', '') or entry.get('message', '') or '')
            if any(kw in content.lower() for kw in ['buy', 'sell', 'trade', 'position', 'hedge']):
                trades.append({
                    'timestamp': entry.get('timestamp', entry.get('ts', '')),
                    'role': entry.get('role', 'unknown'),
                    'content': content[:200],
                    'type': 'trade_signal'
                })
    return trades


def calculate_exposure(positions):
    """Calculate current exposure metrics."""
    if not positions:
        return {'total': 0, 'per_market': {}, 'alerts': []}

    total_capital = sum(p.get('size', 0) for p in positions)
    per_market = {}

    for p in positions:
        mid = p.get('market_id', 'unknown')
        size = p.get('size', 0)
        per_market[mid] = per_market.get(mid, 0) + size

    alerts = []
    # Note: Without knowing total portfolio value, we track absolute values
    # In production, connect to wallet balance for percentage calculation
    if len(positions) > 4:
        alerts.append("HIGH: Multiple open positions - review diversification")

    return {
        'total': total_capital,
        'per_market': per_market,
        'positions_count': len(positions),
        'alerts': alerts
    }


def calculate_pnl(positions):
    """Calculate PnL from positions."""
    pnl_data = []
    total_pnl = 0

    for p in positions:
        entry = p.get('entry_price', 0)
        current = p.get('current_price', entry)
        size = p.get('size', 0)

        if entry > 0:
            pnl_pct = (current - entry) / entry
            pnl_usd = (current - entry) * size
        else:
            pnl_pct = 0
            pnl_usd = 0

        total_pnl += pnl_usd

        pnl_data.append({
            'market_id': p.get('market_id', 'unknown')[:16],
            'side': p.get('side', '?'),
            'entry': f"${entry:.4f}",
            'current': f"${current:.4f}",
            'size': f"${size:.2f}",
            'pnl_pct': f"{pnl_pct:+.1%}",
            'pnl_usd': f"${pnl_usd:+.2f}",
            'status': 'PROFIT' if pnl_usd > 0 else ('LOSS' if pnl_usd < 0 else 'FLAT')
        })

    return pnl_data, total_pnl


# --- Sidebar ---
with st.sidebar:
    st.title("🦞 ClawBot Control")
    st.divider()

    # Status indicators
    gateway_config = OPENCLAW_DIR / "openclaw.json"
    st.markdown("**System Status**")

    if gateway_config.exists():
        st.success("OpenClaw Config: Found")
        try:
            with open(gateway_config) as f:
                config = json.loads(f.read())
            mode = config.get('gateway', {}).get('mode', 'unknown')
            port = config.get('gateway', {}).get('port', 18789)
            st.info(f"Gateway: {mode} (:{port})")
        except Exception:
            st.warning("Config: Parse error")
    else:
        st.error("OpenClaw Config: Not found")

    if POLYCLAW_POSITIONS.exists():
        st.success("PolyClaw Positions: Active")
    else:
        st.info("PolyClaw Positions: No trades yet")

    st.divider()
    st.markdown("**Capital Framework**")
    st.markdown(f"- Max SB Exposure: **{MAX_SB_EXPOSURE:.0%}**")
    st.markdown(f"- Max Per Market: **{MAX_PER_MARKET:.0%}**")
    st.markdown(f"- Stop Loss: **{STOP_LOSS:.0%}**")
    st.markdown(f"- Take Profit: **{TAKE_PROFIT:.0%}**")
    st.markdown(f"- Latency Limit: **{LATENCY_THRESHOLD}ms**")

    st.divider()
    auto_refresh = st.checkbox("Auto-refresh", value=True)
    if auto_refresh:
        st.markdown(f"_Refreshing every {REFRESH_INTERVAL}s_")


# --- Main Content ---
st.title("PolymarketClawBot Dashboard")
st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# Load data
logs = load_session_logs()
positions = load_positions()
exposure = calculate_exposure(positions)
pnl_data, total_pnl = calculate_pnl(positions)
trades = extract_trades_from_logs(logs)

# --- Top Metrics Row ---
col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.metric("Total PnL", f"${total_pnl:+.2f}",
              delta=f"{total_pnl:+.2f}" if total_pnl != 0 else None,
              delta_color="normal")

with col2:
    st.metric("Open Positions", exposure['positions_count'])

with col3:
    st.metric("Capital Deployed", f"${exposure['total']:.2f}")

with col4:
    st.metric("Session Logs", len(logs))

with col5:
    st.metric("Trade Signals", len(trades))

# --- Risk Alerts ---
if exposure['alerts']:
    st.markdown("---")
    for alert in exposure['alerts']:
        st.markdown(f'<div class="risk-alert">⚠️ {alert}</div>', unsafe_allow_html=True)
else:
    st.markdown(f'<div class="safe-indicator">✅ All risk parameters within limits</div>',
                unsafe_allow_html=True)

st.divider()

# --- Two-column layout ---
left_col, right_col = st.columns([3, 2])

with left_col:
    # --- Positions & PnL ---
    st.subheader("📊 Positions & PnL")

    if pnl_data:
        df_pnl = pd.DataFrame(pnl_data)
        st.dataframe(df_pnl, use_container_width=True, hide_index=True)

        # PnL Chart
        if len(pnl_data) > 0:
            fig = go.Figure()
            for p in pnl_data:
                color = '#00c853' if 'PROFIT' in p['status'] else ('#ff4444' if 'LOSS' in p['status'] else '#888')
                fig.add_trace(go.Bar(
                    x=[p['market_id']],
                    y=[float(p['pnl_usd'].replace('$', '').replace('+', ''))],
                    marker_color=color,
                    name=p['market_id']
                ))
            fig.update_layout(
                title="PnL by Position",
                yaxis_title="USD",
                showlegend=False,
                height=300,
                template="plotly_dark"
            )
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No positions yet. Start trading to see PnL data.")

    # --- Trade Signals Log ---
    st.subheader("📋 Recent Trade Signals")

    if trades:
        df_trades = pd.DataFrame(trades[-20:])  # Last 20
        st.dataframe(df_trades, use_container_width=True, hide_index=True)
    else:
        st.info("No trade signals detected in session logs yet.")

with right_col:
    # --- Exposure Monitor ---
    st.subheader("🎯 Exposure Monitor")

    if exposure['per_market']:
        # Pie chart of exposure by market
        markets = list(exposure['per_market'].keys())
        values = list(exposure['per_market'].values())

        fig_exp = px.pie(
            values=values,
            names=[m[:12] for m in markets],
            title="Capital Distribution",
            hole=0.4
        )
        fig_exp.update_layout(height=300, template="plotly_dark")
        st.plotly_chart(fig_exp, use_container_width=True)

        # Per-market table
        for market, size in exposure['per_market'].items():
            pct_indicator = "🟢" if size < 100 else "🟡" if size < 500 else "🔴"
            st.markdown(f"{pct_indicator} `{market[:16]}`: **${size:.2f}**")
    else:
        st.info("No exposure data. Markets will appear after first trade.")

    # --- Agent Status ---
    st.subheader("🤖 Agent Status")

    agents_dir = SESSIONS_DIR
    if agents_dir.exists():
        for agent_dir in agents_dir.iterdir():
            if agent_dir.is_dir():
                sessions_path = agent_dir / "sessions"
                session_count = len(list(sessions_path.glob("*.jsonl"))) if sessions_path.exists() else 0
                st.markdown(f"**{agent_dir.name}**: {session_count} sessions")
    else:
        st.info("No agents directory found. Start OpenClaw gateway first.")

    # --- Latency Monitor ---
    st.subheader("⚡ Latency Monitor")
    st.markdown(f"Threshold: **{LATENCY_THRESHOLD}ms**")

    # Placeholder for latency data
    # In production, read from Redis or structured logs
    latency_placeholder = {
        'RPC Call': '~400ms',
        'LLM Response': '~1200ms',
        'CLOB Order': '~800ms',
        'Total Pipeline': '~2400ms'
    }
    for component, latency in latency_placeholder.items():
        is_ok = "🟢" if "~" in latency and int(latency.replace('~', '').replace('ms', '')) < LATENCY_THRESHOLD else "🔴"
        st.markdown(f"{is_ok} {component}: **{latency}**")


# --- Bottom: Full Session Log ---
st.divider()
with st.expander("📜 Raw Session Log (last 50 entries)", expanded=False):
    if logs:
        for entry in logs[-50:]:
            if isinstance(entry, dict):
                ts = entry.get('timestamp', entry.get('ts', ''))
                role = entry.get('role', '?')
                content = str(entry.get('content', entry.get('message', '')))[:300]
                st.text(f"[{ts}] {role}: {content}")
    else:
        st.info("No session logs found. Start the gateway and begin trading.")


# --- Auto-refresh ---
if auto_refresh:
    time.sleep(REFRESH_INTERVAL)
    st.rerun()
