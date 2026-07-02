# Skill: trading-knowledge

Conhecimento acumulado de trading extraído de vídeos e análises. Leia antes de qualquer tarefa relacionada a mercados financeiros, Polymarket, cripto ou day trade.

## Como usar

1. Leia `~/clawd/docs/trading/frameworks.md` para os frameworks permanentes
2. Leia `~/clawd/docs/trading/README.md` para o índice de vídeos analisados
3. Para contexto recente, verifique `~/clawd/memory/` (entradas marcadas com `[trading]`)

## Categorias cobertas

- **Polymarket** — mercados de predição, estratégias de pricing de probabilidade
- **Cripto** — análise técnica, spot/futuros, gestão de posição
- **Ações/Renda Variável** — análise fundamentalista, swing trade
- **Day Trade / Price Action** — leitura de mercado, tape reading, scalping

## Integração com outras skills

- `polyclaw` — execução em Polymarket (usa os frameworks de probabilidade daqui)
- `polywhale` — análise de posições grandes (combinar com leitura de mercado)
- `latencyninja` — arbitragem de latência (combinar com setups de entrada)
- `polybot-analyzer` — inteligência de bots externos: detecta tipo de estratégia (Temporal Arbitrage, Inventory MM, etc.) de qualquer wallet via data-api do Polymarket

## Pipeline de ingestão

Novos vídeos são processados com:
```bash
python3 ~/clawd/scripts/watch-trading.py <url-youtube-ou-arquivo-local>
```

O script extrai a transcrição, analisa com Claude, e salva automaticamente em:
- `~/clawd/docs/trading/videos/` — análise completa
- `~/clawd/memory/YYYY-MM-DD.md` — sumário na memória diária
- `~/notes/Conhecimento/Trading/` — nota Obsidian (sincroniza com NotebookLM)
