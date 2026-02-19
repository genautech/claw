# API Keys & Model Routing Configuration

## Status — TODOS OS PROVIDERS ATIVOS! ✅

### Providers Configurados

| Provider | Env Var | Auth | Status |
|----------|---------|------|--------|
| Anthropic | `ANTHROPIC_API_KEY` | API Key | ✅ OK |
| OpenAI | `OPENAI_API_KEY` | API Key | ✅ OK |
| OpenAI Codex | OAuth (ChatGPT Plus) | OAuth | ✅ OK |
| Google/Gemini | `GEMINI_API_KEY` | API Key | ✅ OK |
| xAI/Grok | `XAI_API_KEY` | API Key | ✅ OK |
| OpenRouter | `OPENROUTER_API_KEY` | API Key | ✅ OK |
| Polymarket API | `POLYMARKET_API_KEY`<br>`POLYMARKET_API_SECRET`<br>`POLYMARKET_API_PASSPHRASE` | API Key | ✅ OK |

## Estratégia de Custo (Cost-Optimized Routing)

**Última atualização:** 2026-02-18 — Configurado para usar modelos pagos (SuperGrok, Claude, GPT-4o)

### Tier 1 — Agent/Chat (segue instruções, usa tools)

| Modelo | Alias | Input $/M | Output $/M | Uso |
|--------|-------|-----------|------------|-----|
| `xai/grok-4.1` | `/model grok` | ~$0.20 | ~$0.50 | **Primary** — SuperGrok (pago) |
| `anthropic/claude-sonnet-4-5` | `/model sonnet` | $3.00 | $15.00 | **Fallback 1** — melhor em tools/agentes |
| `openai/gpt-4o` | `/model gpt4o` | **GRÁTIS** | **GRÁTIS** | **Fallback 2** — OAuth (ChatGPT Plus) |

### Tier 2 — Analysis/Scanning (disponíveis manualmente)

| Modelo | Alias | Input $/M | Output $/M | Uso |
|--------|-------|-----------|------------|-----|
| `google/gemini-2.5-flash` | `/model flash` | $0.19 | $0.19 | Ultra-barato (removido dos fallbacks) |
| `openrouter/deepseek/deepseek-chat` | `/model deepseek` | $0.28 | $0.42 | 24/7 scanning loops (removido dos fallbacks) |
| `openrouter/deepseek/deepseek-r1` | `/model r1` | $0.55 | $2.19 | Reasoning tasks |

### Fluxo de Failover

```
xai/grok-4.1 (primary - SuperGrok pago)
    ↓ se falhar
anthropic/claude-sonnet-4-5 (Claude pago)
    ↓ se falhar
openai/gpt-4o (grátis via OAuth)
```

### Regras de Economia (Atualizadas)

1. **Chat/Agent (dia-a-dia)**: Grok 4.1 (SuperGrok) — primary, você paga, use-o
2. **Se Grok cair**: Claude Sonnet 4.5 — você paga Claude, use-o
3. **Se tudo cair**: GPT-4o via OAuth — ZERO custo (ChatGPT Plus inclui)
4. **Gemini/DeepSeek removidos dos fallbacks** — disponíveis apenas via `/model flash` ou `/model deepseek` manualmente
5. **Filosofia**: Force uso dos LLMs pagos que você já tem (SuperGrok, Claude, GPT-4o Plus)

## Localização

- **API Keys:** `~/.openclaw/.env` (carregado automaticamente)
- **Config:** `~/.openclaw/openclaw.json`
- **Template:** `config/openclaw-config.json5`

## Trocar Modelo no Chat

```
/model grok      → Grok 4.1 (SuperGrok - PRIMARY)
/model sonnet    → Claude Sonnet 4.5 (Fallback 1)
/model gpt4o     → GPT-4o (Fallback 2 - grátis)
/model flash     → Gemini Flash (disponível manualmente)
/model deepseek  → DeepSeek Chat (disponível manualmente)
/model r1        → DeepSeek R1 (disponível manualmente)
```

## Verificar Status

```bash
openclaw models status
openclaw models list
```

## Credenciais Polymarket API

**Última atualização:** 2026-02-18

As credenciais da API REST do Polymarket estão configuradas em `~/.openclaw/openclaw.json`:

```json
{
  "skills": {
    "entries": {
      "polymarket-exec": {
        "env": {
          "POLYMARKET_API_KEY": "019c6f85-bc2f-7269-a6f8-77fa60e1d6aa",
          "POLYMARKET_API_SECRET": "0b74AWQRZZzEWy-3Wf9Z7UycmSI3anwhUQ8bpFuDEE4=",
          "POLYMARKET_API_PASSPHRASE": "40709d8ca55ecdacaed9514f32ad98921c3d70b080cc99a7546d80aa20256661"
        }
      }
    }
  }
}
```

**Nota:** Essas credenciais são usadas pelo `ClobClientWrapper` para autenticação na API REST do Polymarket. Se não fornecidas, o cliente tentará criar/derivar credenciais automaticamente.
