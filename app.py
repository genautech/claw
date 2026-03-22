"""
PolyAgents Dashboard - Trade & Agent Monitoring
================================================
Run: streamlit run app.py --server.port 8888
URL: http://localhost:8888

Reads from:
- data/simulated_trades.jsonl  (PolyClaw simulated trades)
- data/executions.jsonl        (Polymarket Executor executions)
- data/recommendations.jsonl   (PolyWhale recommendations)
- logs/polymarket-exec.log     (Executor runtime logs)
"""

import streamlit as st
import json
import time
import os
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
from pathlib import Path

# --- Configuration ---
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"

st.set_page_config(
    page_title="PolyAgents Dashboard",
    page_icon="🦞",
    layout="wide",
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
    .agent-card {
        background: rgba(255,255,255,0.03);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 8px;
        padding: 16px;
        margin: 8px 0;
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


# --- Data Loaders ---
def load_jsonl(filepath):
    """Load JSONL or JSON array file (handles mixed formats)."""
    if not filepath.exists():
        return []
    try:
        with open(filepath) as f:
            content = f.read().strip()
            if not content:
                return []
            # Try JSON array first
            if content.startswith('['):
                try:
                    items = json.loads(content)
                    if isinstance(items, list):
                        return items
                except json.JSONDecodeError:
                    pass  # Fall through to JSONL parsing
            # JSONL: one JSON object per line (skip non-JSON lines like '[', ']')
            results = []
            for line in content.split('\n'):
                line = line.strip().rstrip(',')
                if not line or line in ('[', ']'):
                    continue
                try:
                    obj = json.loads(line)
                    if isinstance(obj, dict):
                        results.append(obj)
                except json.JSONDecodeError:
                    continue
            return results
    except Exception:
        return []


def load_log_file(filepath, tail=50):
    """Load last N lines from a log file."""
    if not filepath.exists():
        return []
    try:
        with open(filepath) as f:
            lines = f.readlines()
            return lines[-tail:]
    except Exception:
        return []


def parse_exec_log(lines):
    """Parse executor log lines into structured data."""
    entries = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            parts = line.split(' ', 3)
            if len(parts) >= 3:
                ts = f"{parts[0]} {parts[1].split(',')[0]}"
                level = parts[2].strip('[]')
                msg = parts[3] if len(parts) > 3 else ''
                entries.append({'timestamp': ts, 'level': level, 'message': msg[:200]})
        except Exception:
            entries.append({'timestamp': '', 'level': 'RAW', 'message': line[:200]})
    return entries


# --- Load All Data ---
simulated_trades = load_jsonl(DATA_DIR / "simulated_trades.jsonl")
executions = load_jsonl(DATA_DIR / "executions.jsonl")
recommendations = load_jsonl(DATA_DIR / "recommendations.jsonl")
ninja_trades_raw = load_jsonl(DATA_DIR / "ninja_trades.jsonl")
ninja_spreads = [t for t in ninja_trades_raw if t.get('type') == 'spread_capture']
ninja_summaries = [t for t in ninja_trades_raw if t.get('type') == 'session_summary']
exec_log_lines = load_log_file(LOGS_DIR / "polymarket-exec.log")
exec_log_parsed = parse_exec_log(exec_log_lines)

# --- Sidebar ---
with st.sidebar:
    st.title("🦞 PolyAgents")
    st.divider()

    st.markdown("**Agentes Ativos**")
    ninja_pnl = ninja_summaries[-1].get('simulated_pnl', 0) if ninja_summaries else 0
    agents_info = {
        "PolyClaw": {"icon": "🐾", "status": "Paper Trading", "color": "🟢", "detail": f"{len(simulated_trades)} trades simulados"},
        "PolyWhale": {"icon": "🐋", "status": "Scanning", "color": "🟡", "detail": f"{len(recommendations)} recomendações"},
        "Executor": {"icon": "⚡", "status": "Dry Run (8789)", "color": "🟢", "detail": f"{len(executions)} execuções"},
        "ArbitrageNinja": {"icon": "🥷", "status": "HFT Bot", "color": "🟢" if ninja_spreads else "🟡", "detail": f"{len(ninja_spreads)} spreads | PnL: ${ninja_pnl:.2f}"},
        "LatencyNinja": {"icon": "⏱️", "status": "Monitorando", "color": "🟢", "detail": "Redis cache ativo"},
    }
    for name, info in agents_info.items():
        st.markdown(f"{info['color']} **{info['icon']} {name}** — {info['status']}")
        st.caption(f"   {info['detail']}")

    st.divider()
    st.markdown("**Capital Framework**")
    st.markdown("- Max Exposure: **20%**")
    st.markdown("- Max/Mercado: **5%**")
    st.markdown("- Stop Loss: **-30%**")
    st.markdown("- Take Profit: **+40%**")
    st.markdown("- Latência máx: **3000ms**")

    st.divider()
    auto_refresh = st.checkbox("🔄 Auto-refresh (10s)", value=False)
    if st.button("🔃 Refresh agora"):
        st.rerun()

# --- Header ---
st.title("📊 PolyAgents Dashboard")
st.caption(f"Atualizado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} BRT | Workspace: `{BASE_DIR}`")

# --- Top Metrics Row ---
col1, col2, col3, col4, col5, col6 = st.columns(6)

successful_execs = [e for e in executions if e.get('success')]
failed_execs = [e for e in executions if not e.get('success')]
dry_runs = [e for e in executions if 'dry-run' in str(e.get('action', '')).lower()]
total_volume = sum(e.get('details', {}).get('sizeUsd', 0) for e in executions)
ninja_total_pnl = ninja_summaries[-1].get('simulated_pnl', 0) if ninja_summaries else 0

with col1:
    st.metric("🎯 Trades Simulados", len(simulated_trades))
with col2:
    st.metric("🐋 Recomendações", len(recommendations))
with col3:
    delta_text = f"{len(successful_execs)} ✅ / {len(failed_execs)} ❌" if executions else None
    st.metric("⚡ Execuções", len(executions), delta=delta_text)
with col4:
    st.metric("💰 Volume Total", f"${total_volume:.0f}")
with col5:
    st.metric("🧪 Dry Runs OK", len(dry_runs))
with col6:
    st.metric("🥷 Ninja PnL", f"${ninja_total_pnl:.2f}", delta=f"{len(ninja_spreads)} spreads")

# --- Risk Check ---
if failed_execs:
    st.markdown(f'<div class="risk-alert">⚠️ {len(failed_execs)} execução(ões) com erro — verifique os logs abaixo</div>',
                unsafe_allow_html=True)
else:
    st.markdown('<div class="safe-indicator">✅ Todos os parâmetros de risco dentro dos limites</div>',
                unsafe_allow_html=True)

st.divider()

# --- Main Content: Tabs ---
tab_trades, tab_ninja, tab_exec, tab_recs, tab_logs, tab_agents = st.tabs([
    "🎯 Trades Simulados",
    "🥷 Ninja HFT",
    "⚡ Execuções",
    "🐋 Recomendações",
    "📋 Logs",
    "🤖 Agentes"
])

# --- Tab 1: Simulated Trades ---
with tab_trades:
    st.subheader("Trades Simulados (PolyClaw)")
    if simulated_trades:
        for i, trade in enumerate(simulated_trades):
            with st.container():
                tcol1, tcol2, tcol3, tcol4 = st.columns([3, 1, 1, 1])
                with tcol1:
                    st.markdown(f"**{trade.get('description', 'N/A')}**")
                    st.caption(f"ID: `{trade.get('id', '?')}` | Market: `{trade.get('market_id', '?')}`")
                    st.caption(f"📝 {trade.get('reason', 'Sem razão informada')}")
                with tcol2:
                    decision = trade.get('decision', '?')
                    color_icon = '🟢' if 'BUY' in decision else '🔴'
                    st.markdown(f"{color_icon} **{decision}**")
                    st.markdown(f"Confiança: **{trade.get('confidence', '?')}**")
                with tcol3:
                    st.markdown(f"Target: **${trade.get('targetPrice', 0):.2f}**")
                    st.markdown(f"Edge: **{trade.get('edge', 0):.0%}**")
                    st.markdown(f"Risco: **{trade.get('risk_pct', 0):.1%}**")
                with tcol4:
                    exit_rules = trade.get('exit_rules', {})
                    st.markdown(f"SL: **{exit_rules.get('stop_loss', '?')}**")
                    st.markdown(f"TP: **{exit_rules.get('take_profit', '?')}**")
                    st.markdown(f"Limite: **{exit_rules.get('time_limit', '?')}**")
                    status = trade.get('status', 'UNKNOWN')
                    st.markdown(f"Status: `{status}`")
                if i < len(simulated_trades) - 1:
                    st.markdown("---")

        # Summary chart if multiple trades
        if len(simulated_trades) > 1:
            fig = go.Figure()
            for t in simulated_trades:
                fig.add_trace(go.Bar(
                    x=[t.get('market_id', '?')[:20]],
                    y=[t.get('edge', 0) * 100],
                    marker_color='#00c853' if 'BUY' in t.get('decision', '') else '#ff4444',
                    name=t.get('id', '?')
                ))
            fig.update_layout(
                title="Edge por Trade (%)",
                yaxis_title="Edge %",
                height=300,
                template="plotly_dark",
                showlegend=False
            )
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("🎯 Nenhum trade simulado ainda. O PolyClaw vai registrar aqui quando analisar mercados.")

# --- Tab 2: Ninja HFT ---
with tab_ninja:
    st.subheader("🥷 ArbitrageNinja — High-Frequency Trading Bot")

    if ninja_summaries:
        # Latest session metrics
        last = ninja_summaries[-1]
        ncol1, ncol2, ncol3, ncol4, ncol5 = st.columns(5)
        with ncol1:
            st.metric("⏱️ Duração", f"{last.get('duration_s', 0):.0f}s")
        with ncol2:
            st.metric("📊 Ticks", last.get('ticks', 0))
        with ncol3:
            st.metric("🤑 Oportunidades", last.get('opportunities', 0))
        with ncol4:
            st.metric("💰 PnL Simulado", f"${last.get('simulated_pnl', 0):.2f}")
        with ncol5:
            st.metric("📈 Maior Spread", f"${last.get('max_spread', 0):.4f}")

        st.caption(f"Último mercado: **{last.get('market', 'N/A')}** | Spread médio: ${last.get('avg_spread', 0):.4f}")
        st.markdown("---")

    if ninja_spreads:
        st.markdown("#### 🤑 Spreads Capturados")
        spread_data = []
        for s in ninja_spreads:
            spread_data.append({
                'Hora': s.get('timestamp', '?')[:19],
                'Mercado': str(s.get('market', '?'))[:40],
                'Bid': f"${s.get('best_bid', 0):.4f}",
                'Ask': f"${s.get('best_ask', 0):.4f}",
                'Spread': f"${s.get('spread', 0):.4f}",
                'Profit': f"${s.get('profit', 0):.4f}",
                'PnL Acum.': f"${s.get('cumulative_pnl', 0):.4f}",
                'Tick': s.get('tick', 0),
            })
        st.dataframe(pd.DataFrame(spread_data), use_container_width=True, hide_index=True)

        # PnL chart
        if len(ninja_spreads) > 1:
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=list(range(1, len(ninja_spreads) + 1)),
                y=[s.get('cumulative_pnl', 0) for s in ninja_spreads],
                mode='lines+markers',
                line=dict(color='#00e676', width=2),
                marker=dict(size=6),
                name='PnL Acumulado'
            ))
            fig.update_layout(
                title="PnL Acumulado por Trade (Simulado)",
                xaxis_title="Trade #",
                yaxis_title="PnL ($)",
                height=300,
                template="plotly_dark",
            )
            st.plotly_chart(fig, use_container_width=True)

    elif not ninja_summaries:
        st.info("🥷 Nenhum dado do Ninja ainda. Execute: `python3 scripts/agent_ninja_arbitrage.py --market auto --duration 30`")

    # Session history
    if len(ninja_summaries) > 0:
        with st.expander(f"📋 Histórico de Sessões ({len(ninja_summaries)})"):
            for i, sess in enumerate(reversed(ninja_summaries)):
                st.markdown(f"**Sessão {len(ninja_summaries) - i}** — {sess.get('market', '?')[:50]}")
                st.caption(f"Duração: {sess.get('duration_s', 0)}s | Ticks: {sess.get('ticks', 0)} | Opps: {sess.get('opportunities', 0)} | PnL: ${sess.get('simulated_pnl', 0):.4f}")

with tab_exec:
    st.subheader("Histórico de Execuções (Polymarket Executor)")
    if executions:
        exec_data = []
        for e in executions:
            details = e.get('details', {})
            exec_data.append({
                'Timestamp': e.get('timestamp', '?')[:19],
                'Ação': e.get('action', '?'),
                'Market ID': str(details.get('marketId', '?')),
                'Outcome': details.get('outcomeId', '?'),
                'Side': details.get('side', '?'),
                'Size (USD)': f"${details.get('sizeUsd', 0)}",
                'Max Price': details.get('maxPrice', '?'),
                'Status': '✅ OK' if e.get('success') else '❌ Erro',
            })

        exec_df = pd.DataFrame(exec_data)
        st.dataframe(exec_df, use_container_width=True, hide_index=True)

        # Show errors detail
        if failed_execs:
            st.markdown("#### ❌ Detalhes dos Erros")
            for e in failed_execs:
                error_msg = e.get('error', 'Erro desconhecido')
                st.error(f"**{e.get('action', '?')}** em `{e.get('details', {}).get('marketId', '?')}`: {error_msg[:300]}")

        # Volume chart
        if len(executions) > 0:
            fig = go.Figure()
            for e in executions:
                details = e.get('details', {})
                color = '#00c853' if e.get('success') else '#ff4444'
                label = f"{details.get('marketId', '?')} ({e.get('action', '?')})"
                fig.add_trace(go.Bar(
                    x=[e.get('timestamp', '')[:16]],
                    y=[details.get('sizeUsd', 0)],
                    marker_color=color,
                    text=[label[:30]],
                    textposition='auto',
                ))
            fig.update_layout(
                title="Execuções por Volume (USD)",
                yaxis_title="USD",
                height=300,
                template="plotly_dark",
                showlegend=False
            )
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("⚡ Nenhuma execução registrada ainda. O Executor vai logar aqui.")

# --- Tab 3: Recommendations ---
with tab_recs:
    st.subheader("Recomendações do PolyWhale")
    if recommendations:
        for rec in recommendations:
            with st.expander(f"📊 {rec.get('market_id', '?')[:20]} — {rec.get('decision', '?')}", expanded=True):
                rcol1, rcol2 = st.columns(2)
                with rcol1:
                    st.markdown(f"**Decision:** {rec.get('decision', '?')}")
                    st.markdown(f"**Edge:** {rec.get('edge', 0):.0%}")
                    st.markdown(f"**Confidence:** {rec.get('confidence', '?')}")
                    st.markdown(f"**Risk:** {rec.get('risk_pct', 0):.1%}")
                with rcol2:
                    st.markdown(f"**Target Price:** ${rec.get('targetPrice', 0):.2f}")
                    st.markdown(f"**Reason:** {rec.get('reason', 'N/A')}")
                    sources = rec.get('data_sources', [])
                    st.markdown(f"**Sources:** {', '.join(sources) if sources else 'N/A'}")
    else:
        st.info("🐋 PolyWhale ainda não gerou recomendações. Aguardando scanning de mercados ativos.")

    # Show example format
    with st.expander("📖 Formato esperado de recomendação"):
        st.json({
            "id": "rec_YYYYMMDD_NNN",
            "timestamp": "ISO8601",
            "market_id": "0x...",
            "decision": "BUY_YES | BUY_NO | HEDGE | PASS",
            "targetPrice": 0.62,
            "edge": 0.12,
            "confidence": "HIGH | MEDIUM | LOW",
            "risk_pct": 0.05,
            "reason": "Arbitrage opportunity description",
            "data_sources": ["gamma_api", "kalshi"]
        })

# --- Tab 4: Logs ---
with tab_logs:
    st.subheader("Logs do Polymarket Executor")

    if exec_log_parsed:
        # Summary
        errors = [e for e in exec_log_parsed if e['level'] == 'ERROR']
        warnings = [e for e in exec_log_parsed if e['level'] == 'WARNING']
        infos = [e for e in exec_log_parsed if e['level'] == 'INFO']

        lcol1, lcol2, lcol3 = st.columns(3)
        with lcol1:
            st.metric("INFO", len(infos))
        with lcol2:
            st.metric("WARNING", len(warnings))
        with lcol3:
            st.metric("ERROR", len(errors))

        st.markdown("---")

        # Log entries
        for entry in reversed(exec_log_parsed[-20:]):
            level = entry.get('level', '')
            if level == 'ERROR':
                icon = '🔴'
            elif level == 'WARNING':
                icon = '🟡'
            elif level == 'INFO':
                icon = '🔵'
            else:
                icon = '⚪'

            msg = entry['message']
            # Try to pretty-print TRADE JSON
            if 'TRADE:' in msg:
                try:
                    trade_json = json.loads(msg.split('TRADE: ', 1)[1])
                    st.markdown(f"{icon} `{entry['timestamp']}` **TRADE**")
                    st.json(trade_json)
                except Exception:
                    st.markdown(f"{icon} `{entry['timestamp']}` {msg[:150]}")
            else:
                st.markdown(f"{icon} `{entry['timestamp']}` {msg[:150]}")
    else:
        st.info("📋 Nenhum log do executor encontrado em `logs/polymarket-exec.log`")

    # Raw log view
    with st.expander("📄 Log bruto (últimas 50 linhas)"):
        if exec_log_lines:
            st.code(''.join(exec_log_lines[-50:]), language='text')
        else:
            st.info("Arquivo de log vazio ou não encontrado.")

# --- Tab 5: Agents ---
with tab_agents:
    st.subheader("Status dos Agentes")

    for name, info in agents_info.items():
        with st.container():
            acol1, acol2, acol3 = st.columns([1, 2, 2])
            with acol1:
                st.markdown(f"### {info['icon']} {name}")
                st.markdown(f"{info['color']} **{info['status']}**")
            with acol2:
                st.markdown(f"**Detalhes:** {info['detail']}")
                if name == "PolyClaw":
                    st.markdown("Estratégia: Paper trading simulado")
                    st.markdown("Data: `data/simulated_trades.jsonl`")
                elif name == "PolyWhale":
                    st.markdown("Estratégia: Arb detection, mispricing hunt")
                    st.markdown("Data: `data/recommendations.jsonl`")
                elif name == "Executor":
                    st.markdown("Modo: Dry Run (sem execução real)")
                    st.markdown("API: `http://127.0.0.1:8789`")
                elif name == "LatencyNinja":
                    st.markdown("Cache: Redis local")
                    st.markdown("Threshold: 3000ms")
            with acol3:
                if name == "PolyClaw":
                    st.markdown("**Skills:** polyclaw, polymarket-exec")
                    st.markdown("**Capital Framework:** Enforced ✅")
                elif name == "PolyWhale":
                    st.markdown("**Skills:** polywhale")
                    st.markdown("**Strategies:** 5 (arb, mispricing, carry, weather, whale)")
                elif name == "Executor":
                    st.markdown("**Port:** 8789")
                    st.markdown(f"**Log:** `logs/polymarket-exec.log`")
                elif name == "LatencyNinja":
                    st.markdown("**Skills:** latencyninja")
                    st.markdown("**Monitoring:** API response times")
            st.markdown("---")

    # Data files status
    st.subheader("📁 Arquivos de Dados")
    data_files = [
        ("data/simulated_trades.jsonl", simulated_trades),
        ("data/executions.jsonl", executions),
        ("data/recommendations.jsonl", recommendations),
        ("logs/polymarket-exec.log", exec_log_lines),
    ]
    for fpath, data in data_files:
        full_path = BASE_DIR / fpath
        exists = full_path.exists()
        size = full_path.stat().st_size if exists else 0
        count = len(data)
        icon = '✅' if exists and count > 0 else '⚠️' if exists else '❌'
        st.markdown(f"{icon} `{fpath}` — {'Existe' if exists else 'Não encontrado'} | {size} bytes | {count} registros")

# --- Footer ---
st.divider()
fcol1, fcol2, fcol3 = st.columns(3)
with fcol1:
    st.caption("🦞 PolyAgents Dashboard v1.0")
with fcol2:
    st.caption(f"Data sources: JSONL + logs")
with fcol3:
    st.caption(f"Auto-refresh: {'ON (10s)' if auto_refresh else 'OFF'}")

# --- Auto-refresh ---
if auto_refresh:
    time.sleep(10)
    st.rerun()
