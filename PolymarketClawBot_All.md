# PolymarketClawBot - Consolidated Reference Document

> Master doc with all strategies, research, architecture, agents, LLMs, security, and setup.
> Import into Cursor workspace. Use to spawn agents and guide development.

---

## 1. Vision

Bot hibrido para trading Polymarket via OpenClaw, com Grok para analise profunda e DeepSeek para loops baratos 24/7. Dashboard local (Streamlit localhost:8501) para monitoramento real-time de logs, exposure, trades, e status de agents.

---

## 2. Capital Strategy Separation Framework

### Principio
Separar **Speculative Capital (SB)** de **Constructive Capital (CB)**.

| Dimension | SB (Speculative) | CB (Constructive) |
|-----------|-------------------|---------------------|
| Allocation | 10-20% | 80-90% |
| Horizonte | Short-term, tatico | Long-term, compounding |
| Veiculo | Polymarket trades | Infra, SaaS, automacao |

### Regras SB (Speculative)
- Max 20% do capital liquido
- Zero debt/leverage
- Daily loss limit
- Weekly review obrigatorio
- **Firewalls**: No stress trades, pause 30 dias apos 3 losses semanais

### Regras CB (Constructive)
- Funda automacao e IP
- Build SaaS products
- Compound returns

### Governance
- **Daily**: 15min SB review, 2-4h CB work
- **Weekly**: Performance reviews
- **Monthly**: Shift profits SB -> CB
- **Ladder**: Survival (90% CB) -> Autonomy (CB cash flow)
- **Filter**: Episodico -> SB; Compounding -> CB

---

## 3. OpenClaw v1 Blueprint - Architecture

### Data Flow

```
Fetch Markets -> DeepSeek Scan Hedges -> Grok Perspectiva -> Execute (edge >10%)
```

### Layers
1. **Data Layer**: Odds, macro data, prices (Gamma API, CLOB)
2. **Signal Engine**: Edge detection >8%
3. **Decision Engine**: LLM recommendation (Grok/DeepSeek)
4. **Risk Engine**: 5% per market, -30% exit, +40% partial profit
5. **Execution Engine**: Sign transactions (Polygon)
6. **Logging**: Full trade audit trail

### Stack
- **Runtime**: Node.js (OpenClaw Gateway)
- **Skills**: Python (PolyClaw, custom agents)
- **Database**: JSON logs (built-in), Redis (optional cache)
- **Monitoring**: Streamlit dashboard (localhost:8501)
- **RPC**: Chainstack Polygon node

### Logging Format
```json
{
  "trade_id": "uuid",
  "timestamp": "ISO8601",
  "reason": "edge detected: prob diff 12%",
  "signal_strength": 0.12,
  "capital_used": 50,
  "risk_exposure_after": 0.15
}
```

---

## 4. Polymarket Controlled Trading Plan

### Entry Criteria
- Liquidity > $500k
- Spread tight
- External probability diff > 10% vs market price

### Risk Rules
- Max 20% total exposure
- Max 5% per market
- No leverage ever
- **Exit**: -30% stop loss
- **Profit**: +40% partial take
- **No double down**

### Position Log Format
```json
{
  "market_id": "abc123",
  "entry_price": 0.65,
  "size": 50,
  "reason": "prob imbalance 12% vs Kalshi",
  "exit_rule": "stop -30% or profit +40%"
}
```

---

## 5. Research: Top Traders & Strategies (2026)

### Top Traders
| Trader | PnL | Win Rate | Strategy |
|--------|-----|----------|----------|
| 0x4924... | $3M | - | Arb bots |
| blackwall | $2.8M | - | Politics specialist |
| LucasMeow | $243k | 94.9% | Mispricing hunt |
| tsybka | - | 85.9% | Low volatility |
| BAdiosB | - | 90.8% | Selective trades |
| Theo4/Fredi9999 | $22M | - | High-stakes |
| Weather bots | $65k | - | NOAA data |
| Arb bot | $414k (from $313) | - | Cross-platform arb |

### Strategies Catalog

#### 1. Arb Cross-Platform (Lags 5-15min)
- Exploit price lags between Polymarket, Kalshi, Binance
- Window: 5-15 minutes
- **Priority: HIGH** - PolyWhale primary strategy

#### 2. Weather Mispricing
- NOAA data for city temperature markets
- Statistical edge from forecast accuracy

#### 3. Carry Trades
- Buy longshots early @$0.01
- Sell certainties late near resolution

#### 4. Mispricing Hunt
- Enter last 60 seconds in 90%+ probability locks
- LucasMeow's primary strategy

#### 5. Liquidity Flips / Spread Farming
- Absorb liquidity in bot-dominated markets

#### 6. High-Freq Low-Price
- 200 trades/day at $0.01 increments

#### 7. Expectation Volatility
- Trade crowd emotional swings
- Exit early on sentiment shifts

#### 8. Copy Whales
- Monitor large positions as entry signals

---

## 6. Skills / Agents

### PolyWhale (Elite Analyst)

**Profile**: Trader with 3+ years experience, integrates top strategies.

**Functions**:
- Analyze markets, calculate edge >10%
- Detect manipulation patterns
- Decide: BUY / HEDGE / PASS

**System Prompt**:
```
You are PolyWhale, an elite Polymarket trader. Incorporate strategies from
LucasMeow/tsybka/Theo4: arb lags, mispricing hunt, carry trades, weather
edges, copy whales. Use capital framework: SB cap 20%.

For each market analysis:
1. Fetch odds (Data Layer)
2. Check edge (external vs price >10%)
3. Assess risk (5% max per market)
4. Output JSON:
{
  "decision": "BUY YES|BUY NO|HEDGE|PASS",
  "reason": "max 3 lines",
  "edge": 0.12,
  "confidence": "HIGH|MEDIUM|LOW",
  "risk_pct": 0.05
}

RULES:
- Never exceed 20% total SB exposure
- Never exceed 5% per single market
- Exit at -30% loss, partial profit at +40%
- No revenge trades after losses
- Log everything
```

### LatencyNinja (Latency Engineer)

**Profile**: HFT developer, optimizes for <3s execution.

**Functions**:
- Analyze code for latency bottlenecks
- Suggest async patterns, Redis caching, RPC failover

**System Prompt**:
```
You are LatencyNinja, optimize all code for <3s execution latency.
Priorities:
1. Async RPC calls to Polygon (asyncio, aiohttp)
2. Batch DeepSeek API calls
3. Redis cache for market data (TTL 30s)
4. RPC failover (multiple Chainstack endpoints)

For each optimization:
- Measure simulated latency before/after
- Suggest top 3 optimizations with estimated gains
  (e.g. "Replace sync with asyncio: save ~800ms")
- Prioritize cost/speed ratio
- Ensure no secret leaks in logs/cache

KILL THRESHOLD: If any operation >3s, flag for immediate optimization.
```

---

## 7. LLM Cost-Benefit Analysis (2026)

| Model | Input $/M | Output $/M | Cache $/M | Use Case |
|-------|-----------|------------|-----------|----------|
| DeepSeek | $0.28 | $0.42 | $0.028 | 24/7 scanning loops |
| Grok 4.1 | $0.20 | $0.50 | - | Deep analysis, X sentiment |
| Gemini Flash | $0.19 avg | - | - | Fallback, cheap |
| Claude Haiku | $0.75 | - | - | Reasoning tasks |

**Strategy**: DeepSeek for heavy loops, Grok for deep perspectives.

---

## 8. Security Checklist

- [x] Gateway: `mode: local`, `bind: loopback` (127.0.0.1 only)
- [x] Auth: Token-based, long random string
- [x] mDNS: Minimal mode (no cliPath/sshPort leak)
- [x] DMs: Pairing mode (strangers need approval)
- [x] Tools: Deny automation/runtime/fs groups by default
- [x] Exec: Denied with ask-always policy
- [x] Filesystem: workspaceOnly restriction
- [x] Permissions: 700 on ~/.openclaw, 600 on config
- [x] Logging: Sensitive data redaction enabled
- [x] Keys: All in env vars, never committed
- [x] Wallet: TESTNET only for initial trades
- [x] Session isolation: per-channel-peer
- [x] Never run as root
- [x] Regular `openclaw security audit --deep`

---

## 9. Setup Checklist

### Prerequisites
- [x] Node.js >= 22
- [x] Python 3.11+ with uv
- [x] Git
- [x] OpenClaw installed
- [ ] API keys configured

### Installation Steps
1. `curl -fsSL https://openclaw.ai/install.sh | bash`
2. `openclaw onboard --install-daemon`
3. Configure `~/.openclaw/openclaw.json` (hardened baseline)
4. `chmod 700 ~/.openclaw && chmod 600 ~/.openclaw/openclaw.json`
5. `clawhub install polyclaw && cd ~/.openclaw/skills/polyclaw && uv sync`
6. `openclaw security audit --deep --fix`
7. `openclaw gateway` (start)
8. `streamlit run dashboard/dashboard.py` (monitoring)

### Timeline
- **30 min**: Install + onboard + security
- **Day 1-2**: Spawn PolyWhale, analyze 1 real market
- **Day 3**: Dashboard + monitoring
- **Validation**: Backtest 1 strategy (prob imbalance), require >8% edge

---

## 10. References

- [OpenClaw Official](https://openclaw.ai/)
- [OpenClaw Docs](https://docs.openclaw.ai/)
- [OpenClaw GitHub](https://github.com/openclaw/openclaw)
- [PolyClaw GitHub](https://github.com/chainstacklabs/polyclaw)
- [Chainstack + PolyClaw Tutorial](https://chainstack.com/integrating-chainstack-with-openclaw-bot-for-polymarket)
- [OpenClaw Security Docs](https://docs.openclaw.ai/gateway/security)
