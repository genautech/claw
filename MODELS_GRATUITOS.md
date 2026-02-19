# Models Gratuitos para Testes

## Model Padrão Configurado

**openai/gpt-4o** - Gratuito via OAuth (ChatGPT Plus subscription)

Este é o model padrão agora. Você pode usar no chat sem custos adicionais.

## Como Trocar de Model no Chat

No chat, você pode usar:
- `/model gpt4o` - GPT-4o (gratuito via OAuth)
- `/model grok` - Grok-3 (pago, se quiser usar)
- `/model sonnet` - Claude Sonnet (se tiver créditos)

## Models Disponíveis

### ✅ Gratuitos (via OAuth/Subscription)
- **openai/gpt-4o** - Via ChatGPT Plus OAuth (gratuito se você tem subscription)
- **openai-codex** - Via OAuth (já configurado)

### 💰 Pagos (mas você tem API keys)
- **xai/grok-3** - Via XAI_API_KEY
- **anthropic/claude-sonnet-4-5** - Via ANTHROPIC_API_KEY

### 🌐 Via OpenRouter (centenas de models)
- Acesse via: `openrouter/<provider>/<model>`
- Exemplo: `openrouter/openai/gpt-3.5-turbo` (pode ter modelos gratuitos)

## Configuração Atual

```json
{
  "agents": {
    "defaults": {
      "model": {
        "primary": "openai/gpt-4o",  // ← GRATUITO (OAuth)
        "fallbacks": ["xai/grok-3"]  // Fallback pago
      }
    }
  }
}
```

## Testar no Chat

1. Acesse: `http://127.0.0.1:18789/chat?session=agent%3Amain%3Amain&token=...`
2. O chat usará GPT-4o por padrão (gratuito)
3. Para trocar: digite `/model grok` ou `/model gpt4o`
