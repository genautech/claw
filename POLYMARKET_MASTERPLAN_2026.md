# PolyAgents — Masterplan de Lucratividade 2026

> Revisão técnica + plano de ação para transformar o stack atual (hoje majoritariamente **simulado**) em um sistema que realmente captura edge em prediction markets.
> Autor da revisão: agente Cursor. Data: 2026-06-12. Baseado em leitura do código + pesquisa de mercado (referências no fim).

---

## 0. TL;DR (leia isto primeiro)

1. **O sistema hoje não fatura porque não negocia de verdade.** Os agentes de sinal (`PolyWhale`, `PolyClaw`, `Ninja`) geram recomendações com **valores aleatórios** (`random.uniform`), não com edge real. O dashboard e o executor funcionam, mas alimentados por ruído.
2. **A única estratégia matematicamente sólida que já existe no repo** é o motor de *hedge/coverage* em `references/polyclaw-chainstack/` — e ele **não está plugado** no loop de produção.
3. **O que realmente dá dinheiro em 2026** (com fontes): arbitragem *sum-to-one* / NegRisk com **merge+redeem**, **market making** com rebates, **copy trading** sistemático e **momentum HFT** em mercados cripto de 5–15 min. Nada disso depende de "prever o futuro" — depende de **execução, latência e disciplina de risco**.
4. **Custo de LLM**: hoje só o `hedge.py` usa LLM (modelo grátis OpenRouter). A economia vem de **roteamento por tarefa** (DeepSeek V3.2 / Gemini Flash-Lite para varredura barata; reasoning só quando há edge candidato), não de trocar o modelo do chat.
5. **🚨 CRÍTICO DE SEGURANÇA**: há **credenciais reais commitadas** em `API_KEYS_CONFIG.md` e `.env.template` (API Polymarket, chave DeepSeek, token de gateway). **Rotacione tudo e remova do histórico antes de qualquer outra coisa.**

---

## 1. Diagnóstico honesto do sistema atual

### 1.1 Quem realmente negocia?

| Componente | Negocia na CLOB? | Realidade |
|---|---|---|
| `agent_polywhale.py` | ❌ | Stub: estratégia/edge/decisão **aleatórios** (`random.choice`, `random.uniform(0.03,0.18)`) |
| `agent_polyclaw.py` | ❌ | Paper trade: `fair_value = yes_price + uniform(-0.15,0.15)` |
| `agent_ninja_arbitrage.py` | ❌ | Simula captura de spread; `DRY_RUN` nunca desliga a simulação; nunca chama o executor |
| `polymarket-exec.py` | ✅ (se `DRY_RUN=false` + chaves) | Executor real (GTC buy / FOK sell). Funcional, mas com controles de risco furados (ver 1.3) |
| `brimo.py` | ✅ (vendas) | Gestor de saída TP/SL/trailing real, mas fora do autoloop |
| `references/.../trade.py` | ✅ | PolyClaw "real" (split + CLOB + hedge), **órfão** do loop principal |

**Conclusão:** o pipeline `recommendation → executor → execution` está construído, mas a **fonte do sinal é ruído**. Ligar `DRY_RUN=false` hoje = queimar capital com decisões aleatórias.

### 1.2 LLM: onde está e onde não está

- Único uso real: `references/polyclaw-chainstack/lib/llm_client.py` (OpenRouter, `nvidia/nemotron-nano-9b-v2:free`) consumido **só** por `scripts/hedge.py` para extrair implicações lógicas entre mercados.
- `PolyWhale`/`PolyClaw`/`Ninja`/`Brimo`/`Executor` **não usam LLM** — apesar das SKILLs citarem Grok/DeepSeek/Claude.
- As SKILLs (`skills/polywhale/SKILL.md` etc.) descrevem comportamento **aspiracional** que o código não implementa.

### 1.3 Buracos no motor de risco (`polymarket-exec.py`)

| Controle | Status | Problema |
|---|---|---|
| Reserve floor | ⚠️ carregado, **nunca verificado** em `validate_order` | variável morta |
| Exposição diária | ⚠️ checa o teto, mas **`daily_exposure_usd` nunca é incrementado** após fills | efetivamente sempre 0 → teto inútil |
| Stop loss / take profit | só no `brimo.py` | e Brimo não está no autoloop |
| NegRisk / merge+redeem | ❌ inexistente | sem isso, arbitragem multi-outcome não realiza lucro na hora |
| Slippage / max trade / consecutivos | ✅ ok | funcionam |

### 1.4 Inconsistências estruturais

- Dois sistemas de correção paralelos (`agent_autocorrect.py` ↔ `corrections.jsonl` vs `correction_agent.py` ↔ `approved_corrections.jsonl`), vários no-ops.
- `DRY_RUN` default divergente (executor `false`, Brimo/Ninja `true`) — risco de ligar trade real sem querer.
- 3 cópias do Mission Control (`mission-control/`, `mc-docker/`, `openclaw-mission-control-master/`) + `mission-control.zip` → manutenção dividida.

---

## 2. Tese de lucro: o que realmente funciona em 2026

Resumo da pesquisa (fontes na seção 8). Só **7–17% das carteiras** da Polymarket são lucrativas no longo prazo — e quem ganha são **bots disciplinados**, não apostadores direcionais.

### Estratégia A — Arbitragem *sum-to-one* + NegRisk (risco ~zero) ⭐ começar por aqui
- Binário: se `YES + NO < $1.00` → compra os dois → paga $1.00 na resolução.
- Multi-outcome (NegRisk): se `Σ outcomes < $1.00` → compra todos.
- **Merge + redeem on-chain**: realiza o lucro **imediatamente**, sem esperar resolução.
- Realidade: nos top-50 mercados o spread fecha em ~2.7s (bots sub-100ms dominam). **O edge vive na cauda longa** (mercados pouco vigiados somando 1.03–1.08) e em **cross-venue**.
- Exige spread **> 2.5–3%** para cobrir a taxa de 2% do vencedor + gas.
- Use **FOK em cada leg** (parcial = exposição não-hedgeada). 30–60% das oportunidades não executam — normal.

### Estratégia B — Market making com rebates (o "trabalhador consistente")
- Ordens limite dos dois lados; **makers pagam 0 de fee e recebem 20–25% dos taker fees** como rebate diário (PUSD).
- Stats reportados de bots: **78–85% win rate, 1–3% ao mês, baixa volatilidade**.
- Risco principal: **seleção adversa** (trader informado pega sua cotação velha). Mitigação: limites de inventário (ex. nunca >30% de um lado), alargar spread na volatilidade, **puxar liquidez na notícia**.

### Estratégia C — Copy trading sistemático
- Espelhar carteiras comprovadamente lucrativas via **Data API de posições/trades públicos**.
- O edge é fechar o *gap de execução* que torna o follow manual não-lucrativo (delay 2–5 min para não front-rodar).

### Estratégia D — Momentum/latência HFT em cripto 5–15 min
- Mercados BTC/ETH/SOL Up/Down de curtíssimo prazo: quando a probabilidade real já é ~85% mas o book mostra 50/50, compra certeza barata.
- Milhares de micro-trades diluem variância (bots reportam até 98% win rate nesses nichos).
- Exige **WebSocket** (não polling) e baixa latência.

### Estratégia E — Correlation/logical arb com LLM (o "IQ play")
- LLM lê descrições de mercados e encontra relações lógicas (ex.: "margem de vitória" ⇒ "vencedor") → arbitragem combinatória que humanos não veem.
- **É exatamente o que o `hedge.py`/`coverage.py` já fazem** — falta plugar no loop e dar capital.

> **Portfólio multi-estratégia** é o padrão profissional: MM imprime quando arb morre; correlação domina quando não há notícia; momentum brilha na volatilidade.

---

## 3. Roadmap priorizado (fases técnicas, não cronograma)

Ordenado por **(risco↓, esforço↓, retorno comprovado↑)**.

### Fase 0 — Segurança e fundação (bloqueante)
- **Rotacionar** todas as credenciais expostas (Polymarket API, DeepSeek, gateway token) e **remover do git** (`git filter-repo`/BFG). Mover segredos para `~/.openclaw/.env` (já ignorado) ou Secrets do Cloud Agent.
- Padronizar `DRY_RUN=true` como default em **todos** os componentes; só um *kill switch* explícito liga real.
- Consolidar os dois sistemas de correção em um; arquivar as 3 cópias do Mission Control (manter uma).
- Aprovar contratos USDC.e on-chain (CTF Exchange, NegRisk Exchange, Conditional Tokens, NegRisk Adapter) — pré-requisito para qualquer trade/merge.

### Fase 1 — Arbitragem real (Estratégia A) — primeiro lucro de verdade
- Novo agente `agent_arb.py` (ou reaproveitar `agent_ninja_arbitrage.py`) que:
  1. Assina **WebSocket CLOB** (`wss://ws-subscriptions-clob.polymarket.com/ws/market`) em mercados filtrados por liquidez (>$10k) e resolução <7d.
  2. Detecta `YES+NO<1` e `Σoutcomes<1` (descontando fee+gas+buffer).
  3. Posta **2 legs FOK** via executor e faz **merge+redeem** on-chain.
- Adicionar endpoints/funcs no executor: `negRisk: true` no order quando aplicável; rotina `merge_and_redeem`.
- **Corrigir os controles de risco furados** (incrementar `daily_exposure_usd`; enforce reserve floor) — pré-requisito de segurança para ligar real.

### Fase 2 — Motor de risco unificado (Brimo 2.0)
- Centralizar TP/SL/trailing/reserve/exposição num módulo único usado por executor **e** monitor.
- **Kelly fracionário** para sizing; **circuit breakers** (perda por sessão/hora, inventário, latência).
- Saldo real on-chain (USDC.e via `wallet_manager.py`) como base do reserve floor — não `capitalInitial` fake.
- Colocar Brimo no autoloop.

### Fase 3 — Correlation arb com LLM (Estratégia E) + Copy trading (C)
- Plugar `hedge.py`/`coverage.py` no loop; rotear o LLM (ver seção 4).
- Novo `agent_copytrader.py`: ranqueia carteiras via Data API (PnL/win-rate/drawdown), espelha entradas com delay e caps.

### Fase 4 — Market making (Estratégia B)
- `agent_mm.py`: ladders dos dois lados, limites de inventário, recuo na volatilidade, captura de rebate.
- Só depois das Fases 1–2 (precisa de risco sólido e baixa latência).

### Fase 5 — Infra de latência
- VPS em **Amsterdam** (matching engine colocalizado, ~1.2ms) + RPC privado (Polygon).
- Métricas: tempo detecção→ordem, fill-rate, PnL por estratégia.

---

## 4. LLMs 2026 — redução de custo + efetividade

**Princípio:** não existe "melhor modelo", existe **roteador por tarefa**. Caching + batch cortam 50–95%.

### Tabela de referência (preços ~jun/2026, USD por 1M tokens)

| Modelo | Input | Output | Papel sugerido no stack |
|---|---|---|---|
| Gemini 2.x Flash-Lite | ~$0.075–0.10 | ~$0.30–0.40 | **Varredura 24/7** (classificar/filtrar mercados, extrair campos) |
| DeepSeek V3.2 | ~$0.14–0.28 | ~$0.28–0.42 | **Workhorse barato** (resumo de notícia, parsing de descrição) — cache 90% |
| Mistral Nemo/Small | ~$0.02–0.20 | ~$0.04–0.60 | Classificação/roteamento ultra-barato |
| DeepSeek R1 | ~$0.55 | ~$2.19 | **Reasoning de correlação/implicação lógica** (só em candidatos com edge) |
| GPT-5.x mini / nano | ~$0.05–0.75 | ~$0.40–4.50 | Tool-calling/decisão estruturada de média complexidade |
| Claude Haiku 4.5 | ~$0.25–1.00 | ~$1.25–5.00 | Saída estruturada rápida; cache 90% |
| Claude Sonnet / GPT-5.x | $2.50–3.00 | $10–15 | **Só** casos difíceis / revisão final (raro) |

### Arquitetura de roteamento (a construir)
```
Tarefa → Router (heurística + custo)
  ├─ varredura/classificação em massa  → Gemini Flash-Lite / Mistral
  ├─ parsing/resumo de descrição/news → DeepSeek V3.2 (cache on)
  ├─ correlação/implicação lógica      → DeepSeek R1 (só p/ candidatos)
  └─ decisão crítica/ambígua           → GPT-5.x mini / Claude Haiku
```
- **Caching de prompt**: descrições de mercado mudam pouco → cache hit barateia 90%.
- **Batch**: varredura noturna em lote (−50%).
- **Generalizar `llm_client.py`**: hoje é OpenRouter-only e single-model. Tornar multi-provider + seleção por tarefa + contagem de custo por chamada (logar em `data/llm_costs.jsonl`).
- **Regra de ouro**: LLM **nunca** decide tamanho de posição sozinho; ele gera *candidatos*; a matemática (arb/coverage/Kelly) decide.

---

## 5. Ferramentas, MCPs e APIs

### 5.1 APIs Polymarket (usar de verdade)
- **CLOB** (`clob.polymarket.com`) via `py-clob-client 0.34.6` — ordens GTC/GTD/FOK/FAK; auth HMAC-SHA256 derivada da chave (`create_or_derive_api_creds`).
- **WebSocket** (`wss://ws-subscriptions-clob...`) — orderbook em tempo real (já usado pelo Ninja; expandir).
- **Gamma** — metadados; **sempre** ler `outcomes[]`/`clobTokenIds[]` por índice casado (não assumir index 0 = "Yes"); checar flag **`negRisk`**.
- **Data API** (`data-api.polymarket.com/positions`) — posições/trades públicos → base do copy trading.
- Gotcha clássico: **mapeamento `condition_id → token_id`** entre Gamma e CLOB. Resolver isso primeiro.

### 5.2 Fontes externas (edge cross-venue / informação)
- **Kalshi**, **Binance/derivativos**, **Manifold** → arbitragem cross-venue e âncora de probabilidade.
- **NOAA** (clima), feeds de notícia/X → sinais de mispricing.
- **Dune Analytics** → dashboards para achar carteiras lucrativas e medir spreads.

### 5.3 MCPs
- Hoje disponíveis no ambiente: **Context7** (docs), **Sanity**, **GitHub**. Nenhum específico de trading.
- **Proposta:** construir um **MCP server "polymarket"** expondo tools tipadas: `list_markets`, `get_orderbook`, `find_arbitrage`, `get_wallet_positions`, `place_order` (com guarda `DRY_RUN`). Isso deixa qualquer agente/chat operar com segurança e padroniza acesso.
- Usar **Context7 MCP** para manter `py-clob-client`/web3 atualizados ao codar.

---

## 6. Métricas de sucesso e gestão de risco

- **Por estratégia**: PnL líquido (pós fee+gas), win-rate, fill-rate, Sharpe, max drawdown, latência detecção→ordem.
- **Risco rígido**: cap por mercado, cap de exposição diária (corrigir o contador!), reserve floor on-chain, perda máx por sessão/hora (circuit breaker), limite de inventário (MM).
- **Sizing**: Kelly fracionário (¼–½ Kelly), nunca full Kelly.
- **Resolução UMA**: disputas existem; manter buffer no sizing (um arb "ganho" pode ser re-resolvido).
- **Backtest/paper first**: validar cada agente em `DRY_RUN` com dados reais antes de capital. Hoje os JSONL são ruído → recriar com sinais reais.

---

## 7. Primeiros passos acionáveis (o que eu posso implementar a seguir)

Posso atacar qualquer um destes — diga qual priorizar:
1. **Fase 0 — Segurança**: PR removendo segredos do repo + `.env.template` sanitizado + checklist de rotação. *(rápido, alto impacto)*
2. **Correções de risco do executor**: incrementar exposição diária, enforce reserve floor, padronizar `DRY_RUN`, suporte `negRisk`. *(médio)*
3. **`agent_arb.py` (Estratégia A)**: detector real de `YES+NO<1` / `Σ<1` via WebSocket + merge/redeem, rodando em `DRY_RUN` com dados reais. *(maior, é o caminho do primeiro lucro)*
4. **Router de LLM multi-provider** com logging de custo. *(médio)*
5. **MCP server "polymarket"**. *(médio)*

---

## 8. Referências (pesquisa 2026)

**Estratégias / mercado**
- "The Most Profitable Polymarket Trading Strategy in 2026" — dev.to/xniiinx
- "Beyond Simple Arbitrage: 4 Strategies Bots Actually Profit From" — Medium/ILLUMINATION
- "Arbitrage Bots Dominate Polymarket With Millions in Profits" — Yahoo Finance
- "Market Making on Polymarket" — startpolymarket.com/strategies/market-making
- "Polymarket HFT: How Traders Use AI to Identify Arbitrage" — quantvps.com

**Implementação técnica**
- "How to Build a Polymarket Arbitrage Bot (2026)" — blog.getnick.ai
- Polymarket API Guide (CLOB/REST, 2026) — ordens FOK p/ legs, NegRisk adapter
- Repos: `BlackCandleLab/polymarket-trading-bot`, `kmizzi/karb`, `roswelly/polymarket-arbitrage-bot` (merge/redeem, 5 estratégias)

**Custo de LLM**
- LLM API Pricing 2026 — apiscout.dev, fungies.io, tldl.io, tokenmix.ai (DeepSeek V3.2, Gemini Flash-Lite, GPT-5.x mini, Claude Haiku 4.5)

> ⚠️ Nada aqui é conselho financeiro. Prediction markets têm risco real (slippage, gas, disputa de oráculo, seleção adversa). Comece pequeno, em `DRY_RUN`, e só escale o que provar PnL líquido positivo.
