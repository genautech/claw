# Teste LLMs Pagos - Instruções

**Data:** 2026-02-18  
**Status:** Configuração aplicada, aguardando teste manual

## Configuração Aplicada

✅ **Primary:** `xai/grok-4.1` (SuperGrok)  
✅ **Fallback 1:** `anthropic/claude-sonnet-4-5` (Claude)  
✅ **Fallback 2:** `openai/gpt-4o` (GPT-4o via OAuth)  
✅ **Removidos:** Gemini e DeepSeek dos fallbacks

**Arquivo:** `~/.openclaw/openclaw.json`  
**Gateway:** Reiniciado e rodando (porta 18789)

## Teste Manual (Telegram/Discord)

### Passo 1: Trocar Modelo
No Telegram ou Discord, envie:
```
/model grok
```
(ou `/model sonnet` ou `/model gpt4o` para testar outros pagos)

### Passo 2: Executar Prompt Betty 2.0
Cole o prompt completo que você mencionou (com circuit breaker, regime filter, etc.):

```
scan Polymarket trending markets, calc edge em 3 crypto Up/Down, propose first paper trade with $1 simulado
```

### Passo 3: Registrar Resultados
Anote:
- **Modelo usado:** (grok/sonnet/gpt4o)
- **Output completo:** (resposta do agente)
- **Tokens usados:** (se disponível nos logs)
- **Tempo de resposta:** (latência)
- **Qualidade da análise:** (edge calculado, trades propostos)

## Verificar Logs

```bash
# Logs do gateway
tail -f ~/.openclaw/logs/openclaw-*.log

# Ou via comando
openclaw gateway logs
```

## Status Atual

- ✅ Gateway: Rodando (OK)
- ✅ Telegram: Configurado
- ✅ WhatsApp: Linked
- ⏳ Teste manual: Pendente

---

**Nota:** Se `grok-4.1` não funcionar (modelo não encontrado), tente `xai/grok-3` que está no alias. O OpenClaw pode não ter suporte para grok-4.1 ainda.
