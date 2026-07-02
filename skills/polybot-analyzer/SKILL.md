---
name: polybot-analyzer
description: Analyze Polymarket bot trades using Claude. Implement the 5 proven bot strategies (Dynamic Rotation, Temporal Arbitrage, Inventory Market-Making, Hedged Directional, Late-Resolution Capture) with Bayesian probability updates, Kelly sizing, and Avellaneda–Stoikov inventory management.
version: 1.0.0
author: genau@yoobe.co
requirements:
  - python3
tags:
  - polymarket
  - trading
  - bot-analysis
  - crypto
  - prediction-markets
  - bayesian
---

# Polybot Analyzer: Análise de Bots no Polymarket com Claude

Este skill te transforma em um analisador de estratégias de trading bots no Polymarket. Baseado na análise de 10M+ execuções reais, você implementa os modelos matemáticos que separam bots lucrativos dos demais.

> **REFERÊNCIA**: Análise original por @Dan1ro0 — 1.000+ wallets, 10M+ trades nos mercados crypto Up/Down do Polymarket.

---

## Fontes de Dados Reais (sem auth)

### Atividade de qualquer wallet
```bash
curl "https://data-api.polymarket.com/activity?user={WALLET_ADDRESS}&limit=100"
```
Campos úteis: `timestamp`, `title`, `side` (BUY/SELL), `size`, `usdcSize`, `price`, `outcomeIndex` (0=Up/Yes, 1=Down/No), `conditionId`

### Posições abertas de qualquer wallet
```bash
curl "https://data-api.polymarket.com/positions?user={WALLET_ADDRESS}"
```
Campos úteis: `size`, `avgPrice`, `currentValue`, `cashPnl`, `outcome`, `title`, `conditionId`

### Mercados crypto Up/Down ativos
```bash
curl "https://gamma-api.polymarket.com/markets?active=true&limit=20&order=volume24hr&ascending=false"
```
Campos úteis: `question`, `outcomePrices`, `clobTokenIds`, `liquidity`, `volume24hr`, `conditionId`

> Para análise automatizada, use o script `scripts/agent_polybot_analyzer.py`:
> ```bash
> python3 scripts/agent_polybot_analyzer.py {WALLET_ADDRESS}
> ```

---

## O Que Este Skill Faz

1. **Calcula desequilíbrio de order book** (sinal primário)
2. **Atualiza probabilidade via Bayes** após novos sinais
3. **Calcula edge líquido** descontando fees, slippage e incerteza
4. **Detecta dislocações entre mercados relacionados** (z-score)
5. **Seleciona estrutura de posição** entre as 5 estratégias
6. **Dimensiona posição via Kelly fracionário**
7. **Ajusta quotes por inventário** (modelo Avellaneda–Stoikov)

---

## 1. Sinal: Desequilíbrio de Order Book

O primeiro sinal que um bot calcula direto do livro de ordens:

```python
def orderbook_imbalance(bids, asks):
    bid_volume = sum(size for price, size in bids)
    ask_volume = sum(size for price, size in asks)
    total_volume = bid_volume + ask_volume
    if total_volume == 0:
        return 0.0
    return (bid_volume - ask_volume) / total_volume
```

- **Positivo**: mais volume comprador → pressão para Up
- **Negativo**: mais volume vendedor → pressão para Down
- Sozinho, não é suficiente — combinar com movimento de preço, volume e tempo restante

---

## 2. Atualização de Probabilidade via Bayes

Após receber um sinal, o bot atualiza a probabilidade do resultado:

```python
def bayes_update(prior_up, signal_given_up, signal_given_down):
    numerator = signal_given_up * prior_up
    denominator = numerator + signal_given_down * (1 - prior_up)
    return numerator / denominator
```

**Exemplo prático**:
- `prior_up = 0.41` (mercado precifica Up em 41¢)
- `signal_given_up = 0.64` (sinal aparece em 64% dos cenários Up históricos)
- `signal_given_down = 0.35`
- → Probabilidade posterior: ~56%
- → Edge bruto: 56% - 41¢ = **15 pontos percentuais**

**Atenção**: movimento de preço + volume + desequilíbrio podem parecer 3 sinais independentes mas são 3 efeitos do mesmo evento. Evitar double-counting.

---

## 3. Edge Líquido (após custos reais)

Edge bruto não é lucrativo automaticamente — o bot calcula o que sobra após execução real:

```python
def calculate_net_edge(model_probability, execution_price, fee, slippage, safety_buffer):
    gross_edge = model_probability - execution_price
    net_edge = gross_edge - fee - slippage - safety_buffer
    return gross_edge, net_edge
```

**Parâmetros típicos**:
- `fee`: 1.7% (taker fee Polymarket)
- `slippage`: 0.5%
- `safety_buffer`: 1.0% (incerteza do modelo)

Se `net_edge <= 0`, não há trade.

---

## 4. Detecção de Dislocação entre Mercados (Z-Score)

Mercados relacionados (BTC 5m, BTC 15m, ETH 5m) não atualizam na mesma velocidade. O bot mede quando o spread está fora do normal:

```python
def spread_zscore(current_spread, average_spread, spread_deviation):
    return (current_spread - average_spread) / spread_deviation
```

- **Z > 3**: spread muito fora do histórico → possível oportunidade
- Não garante trade — um mercado pode genuinamente estar atrasado
- Comparar sempre contra o modelo de fair value de cada contrato, não apenas os preços absolutos de Up

---

## 5. As 5 Estratégias de Posição

### 5.1 Dynamic Position Rotation (Rotação Dinâmica)

O bot atualiza sua visão e pode mudar de direção várias vezes na mesma janela.

**Quando usar**: mercado volátil com múltiplos sinais durante a janela
**Risco**: reversões falsas repetidas consomem o edge em custos de execução
**Regra**: só mudar de direção quando novo sinal cobre custo de saída + reconstrução + risco de estar errado novamente

```
Lógica:
1. Acumula Up via limit orders
2. Sinal enfraquece → vende parte do Up, cancela ordens restantes
3. Acumula Down
4. Sinal reverte → reconstrói Up
```

### 5.2 Temporal Arbitrage (Arbitragem Temporal)

Monta os dois lados em momentos diferentes quando os preços estão favoráveis.

**Exemplo**:
- BTC cai forte → Down em 26¢ → compra 750 Down @ avg 27.4¢
- BTC recupera → Up em 49¢ → compra 750 Up @ avg 49.8¢
- Par completo: 27.4¢ + 49.8¢ = **77.2¢** → margem bruta 22.8¢

**Risco**: posição unilateral enquanto espera o segundo lado
**Melhor ambiente**: mercados com múltiplos movimentos nos dois sentidos
**Pior ambiente**: tendência unidirecional prolongada

### 5.3 Inventory Market-Making (Market Maker de Inventário)

Gerencia inventário total de contratos através de múltiplos mercados e timeframes.

**Estrutura**:
- Compra e vende em pequenos lotes, rastreando custo médio total
- Perto do vencimento: pode vender o lado caro, liberar capital, comprar o lado barato como hedge de baixo custo
- Opera BTC/ETH/SOL em 5m/15m/1h/4h simultaneamente

**Desafio**: se custo médio do par (Up + Down) > $1, o sistema tem margem negativa garantida. Precisa recuperar via venda de inventário caro, rebates de maker, ou eficiência de capital.

### 5.4 Hedged Directional (Direcional com Hedge)

Mantém uma base protegida + lean direcional.

```python
def inspect_position(up_quantity, down_quantity, up_average_price, down_average_price):
    protected_pairs = min(up_quantity, down_quantity)
    directional_up = max(up_quantity - down_quantity, 0)
    directional_down = max(down_quantity - up_quantity, 0)
    pair_cost = up_average_price + down_average_price
    return {
        "protected_pairs": protected_pairs,
        "extra_up": directional_up,
        "extra_down": directional_down,
        "average_pair_cost": pair_cost,
        "pair_margin": 1 - pair_cost
    }
```

**Exemplo**: 280 Up + 257 Down
- 257 pares protegidos → garantem $257 independente do resultado
- 23 Up extras → lean direcional se o modelo favorece Up

**Atenção**: hedge caro (par > $1) pode ser menos eficiente que posição direcional menor.

### 5.5 Late-Resolution Capture (Captura de Resolução Final)

Foca exclusivamente nos últimos segundos — compra o lado favorito a 98-99¢.

**Mecânica**: entrada @ 98.6¢ → payout $1 → lucro 1.4¢/contrato

**Requisitos**:
- Saber exatamente qual feed determina o resultado
- Saber distância atual do preço em relação ao boundary do contrato
- Volume alto para compensar margem pequena por operação

**Risco**: 1 resolução incorreta pode apagar 99 operações corretas

---

## 6. Gestão de Inventário (Avellaneda–Stoikov Simplificado)

O preço de reserva ajusta as quotes com base no inventário atual:

```python
def reservation_price(fair_price, inventory, risk_aversion, volatility, time_remaining):
    inventory_adjustment = inventory * risk_aversion * volatility**2 * time_remaining
    return fair_price - inventory_adjustment
```

- Se o bot já tem muito Up → fica menos agressivo para comprar mais Up
- Ao mesmo tempo, fica mais agressivo para adquirir Down (reduz desequilíbrio)

**Tipos de ordem importantes**:
- `GTC` — fica ativo até cancelar
- `GTD` — expira em tempo específico
- `FOK` — preenche tudo ou cancela
- `FAK` — preenche o disponível, cancela o resto
- `Post-only` — garante que adiciona liquidez (maker rebate)

---

## 7. Dimensionamento via Kelly Fracionário

```python
def fractional_kelly(win_probability, entry_price, fraction=0.25):
    lose_probability = 1 - win_probability
    net_odds = (1 - entry_price) / entry_price
    full_kelly = (net_odds * win_probability - lose_probability) / net_odds
    return max(full_kelly * fraction, 0)
```

- `fraction=0.25` = 1/4 Kelly (padrão conservador)
- Reduz chance de uma estimativa incorreta causar dano grave

**Limites adicionais obrigatórios**:
- Tamanho máximo por posição
- Exposição máxima por ativo
- Limite de inventário não-hedgeado
- Daily loss limit
- Emergency shutdown se dados ficarem não-confiáveis

**Correlação**: BTC 5m, BTC 15m, ETH 5m e SOL 5m podem todas perder valor juntas durante um movimento macro. O risk manager controla exposição correlacionada, não apenas por posição individual.

---

## 8. Stack Completo do Bot

```
Layer 1 — Market Data
  Preços externos, feed de resolução oficial, order books ao vivo,
  execuções recentes, status das suas próprias ordens

Layer 2 — Signals
  Movimento de preço, volume, volatilidade, desequilíbrio do book,
  dislocações entre mercados relacionados

Layer 3 — Probability
  Modelo atualiza fair probability quando chega informação relevante

Layer 4 — Position Logic
  Escolhe entre: rotation, temporal arbitrage, inventory,
  directional hedge, ou late-resolution

Layer 5 — Execution & Risk
  Ordens colocadas, canceladas e ajustadas com inventário
  e tamanho dentro dos limites

Layer 6 — Research (Claude)
  Analisa histórico de trades, identifica estruturas recorrentes,
  escreve backtests, estuda ciclos mal-sucedidos
```

**Loop principal**:

```python
async def run_bot():
    while True:
        state = await receive_market_update()
        signal = build_signal(state)
        probability = update_probability_model(state, signal)
        edge = scan_for_edge(state, probability)
        if not edge["tradable"]:
            continue
        position_plan = choose_position_model(state, edge)
        orders = build_execution_plan(state, position_plan)
        if risk_manager_approves(orders, state):
            await send_orders(orders)
```

O loop de baixa latência deve ser **determinístico**: recebe dados → aplica regras → verifica limites → envia ordem. Claude entra na Layer 6 (Research), não no loop principal.

---

## 9. Como Usar Este Skill

### Analisar uma Wallet de Bot

Peça para Claude:
1. Reconstruir o ciclo de vida completo dos trades (não olhar posição final isolada)
2. Identificar qual das 5 estratégias o bot usa
3. Calcular custo médio dos pares (Up + Down)
4. Verificar se margem é positiva após custos

### Avaliar uma Oportunidade

Dados necessários:
- Preço atual de Up e Down
- Order book (bids e asks com volumes)
- Preço do Bitcoin e velocidade do movimento
- Tempo restante no contrato
- Histórico de sinais similares (signal_given_up, signal_given_down)

Sequência:
1. `orderbook_imbalance()` → sinal inicial
2. `bayes_update()` → probabilidade posterior
3. `calculate_net_edge()` → edge líquido real
4. `spread_zscore()` → verificar mercados relacionados
5. `choose_position_model()` → estratégia adequada
6. `fractional_kelly()` → tamanho da posição
7. `reservation_price()` → ajustar quotes por inventário

### Identificar Por Que um Bot Perdeu

1. Snapshot final não basta — rastrear como a posição foi construída
2. Verificar custo médio do par ao longo do tempo
3. Identificar se houve signal double-counting (mesmo evento contado múltiplas vezes)
4. Verificar se edge bruto era positivo mas net edge era negativo (subestimativa de custos)
5. Verificar correlação com outros mercados na mesma sessão

---

---

## 10. Detectar Tipo de Bot pela Atividade Real

### Passo 1: Buscar atividade da wallet

```python
import httpx, asyncio

async def get_activity(wallet: str, limit=100):
    async with httpx.AsyncClient() as c:
        r = await c.get(
            f"https://data-api.polymarket.com/activity?user={wallet}&limit={limit}"
        )
        return r.json()

async def get_positions(wallet: str):
    async with httpx.AsyncClient() as c:
        r = await c.get(
            f"https://data-api.polymarket.com/positions?user={wallet}"
        )
        return r.json()
```

### Passo 2: Detectar execução simultânea (bot confirmado)

```python
from collections import defaultdict

def detect_simultaneous(trades):
    by_ts = defaultdict(list)
    for t in trades:
        by_ts[t['timestamp']].append(t)
    simultaneous = {ts: ts_trades for ts, ts_trades in by_ts.items() if len(ts_trades) > 1}
    bot_ratio = len(simultaneous) / len(by_ts) if by_ts else 0
    return simultaneous, bot_ratio

# bot_ratio > 0.10 → bot confirmado (>10% dos timestamps têm múltiplos trades)
```

### Passo 3: Reconstruir pares Up/Down por mercado

```python
def reconstruct_pairs(trades):
    by_market = defaultdict(lambda: {'up': [], 'down': []})
    for t in trades:
        if t.get('side') != 'BUY':
            continue
        side_key = 'up' if t.get('outcomeIndex', 0) == 0 else 'down'
        by_market[t['conditionId']][side_key].append(float(t['price']))

    pairs = {}
    for cid, sides in by_market.items():
        if sides['up'] and sides['down']:
            avg_up = sum(sides['up']) / len(sides['up'])
            avg_down = sum(sides['down']) / len(sides['down'])
            pair_cost = avg_up + avg_down
            pairs[cid] = {
                'avg_up': round(avg_up, 4),
                'avg_down': round(avg_down, 4),
                'pair_cost': round(pair_cost, 4),
                'margin': round(1 - pair_cost, 4),
                'n_up_trades': len(sides['up']),
                'n_down_trades': len(sides['down']),
            }
    return pairs
```

### Passo 4: Classificar estratégia pelos padrões detectados

| Padrão | Estratégia |
|---|---|
| >10% timestamps duplicados + trades em BTC/ETH/SOL/XRP simultâneos | **5.3 Inventory Market-Making** |
| Pares Up+Down com timestamps muito distantes (>60s) | **5.2 Temporal Arbitrage** |
| Sequência BUY Up → SELL Up → BUY Down no mesmo `conditionId` em <30s | **5.1 Dynamic Rotation** |
| Trades com `price > 0.97` nos últimos 60s antes de resolução | **5.5 Late-Resolution Capture** |
| Par com excesso consistente em um lado (ex: 280 Up / 257 Down) | **5.4 Hedged Directional** |

### Passo 5: Estimar parâmetros do bot

```python
def estimate_bot_params(pairs):
    margins = [p['margin'] for p in pairs.values() if p['margin'] > -0.5]
    if not margins:
        return {}
    avg_margin = sum(margins) / len(margins)
    profitable_pairs = sum(1 for m in margins if m > 0)
    return {
        'avg_pair_margin': round(avg_margin, 4),
        'profitable_pair_pct': round(profitable_pairs / len(margins) * 100, 1),
        'implied_fee_slippage': round(avg_margin * -1, 4) if avg_margin < 0 else 0,
        'estimated_kelly_fraction': round(max(0.1, min(0.5, avg_margin * 10)), 2),
    }
```

---

## 11. Integração com o Ecossistema Clawd

### O que fazer com o resultado
- **Gravar em** `memory/YYYY-MM-DD.md` com tag `[bot-analysis]` para uso em sessões futuras
- **Calibrar** `data/dashboard-config.json` com `minEdge` e `minConfidence` baseados nos parâmetros detectados
- **NÃO gravar em** `data/recommendations.jsonl` — esse é domínio exclusivo do PolyWhale

### Exemplo de entrada na memória
```markdown
[bot-analysis] 2026-07-01 — Wallet bonereaper
Tipo: Inventory Market-Making (5.3)
Ativos: BTC/ETH/SOL 5m simultâneos
Bot ratio: 34% (timestamps duplicados)
Avg pair cost: 0.812 → margem bruta 18.8%
Pairs analisados: 23 | Lucrativos: 19 (82.6%)
Implied fees+slippage: ~3.2%
Calibração sugerida: minEdge=8, Kelly=0.25
```

### Como usar para melhorar o próprio bot
1. Se `avg_pair_margin > 0.15` → bot está capturando dislocações grandes, mercado tem liquidez
2. Se `bot_ratio > 0.30` → competição alta nessa janela, aumentar velocidade ou mudar timeframe
3. Se maioria usa Late-Resolution Capture → garantir que o executor tem latência < 500ms perto do vencimento

---

## Conclusão

Bots lucrativos no Polymarket não "preveem" onde o Bitcoin vai estar em 5 minutos.

Eles são **mais rápidos em calcular o que cada resultado possível deveria valer agora**.

A fórmula central:
```
dados confiáveis
→ estimativa de probabilidade independente
→ edge após custos
→ estrutura de posição correta
→ execução precisa
→ risco controlado
→ lucro
```
