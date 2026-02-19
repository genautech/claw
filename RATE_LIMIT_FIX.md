# Rate Limit Fix - Instruções

## Problema
API rate limit atingido. Isso pode acontecer quando:
- Muitas sessões ativas fazendo requisições simultâneas
- Heartbeats muito frequentes
- Dashboard fazendo polling muito rápido
- Loops sem delays adequados

## Soluções Imediatas

### 1. Reduzir Frequência de Heartbeats
- Heartbeats padrão: a cada 30 minutos
- Se estiver muito frequente, aumentar intervalo

### 2. Adicionar Delays em Loops
- Sempre adicionar `await sleep(1000)` ou similar em loops
- Não fazer requisições em paralelo sem controle

### 3. Usar Modelos Mais Baratos/Gratuitos
- GPT-4o (OAuth) tem limites mesmo sendo "gratuito"
- Considerar usar Gemini Flash para tarefas menos críticas
- DeepSeek via OpenRouter para scanning

### 4. Verificar Sessões Ativas
- Fechar sessões não utilizadas
- Limitar número de sessões simultâneas

### 5. Implementar Exponential Backoff
- Quando receber 429, esperar antes de retry
- Aumentar tempo de espera progressivamente

## Configuração Recomendada

```json
{
  "agents": {
    "defaults": {
      "model": {
        "primary": "openai/gpt-4o",
        "fallbacks": ["google/gemini-2.5-flash"]  // Usar Gemini como fallback (mais barato)
      }
    }
  }
}
```

## Para o Agente

Quando receber rate limit:
1. **Pare imediatamente** - não continue fazendo requisições
2. **Espere 60 segundos** antes de retry
3. **Use fallback model** se disponível
4. **Documente** o erro em memory/YYYY-MM-DD.md
5. **Reduza frequência** de operações que causaram o limite
