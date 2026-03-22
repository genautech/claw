# Como Usar o OpenClaw - Guia Completo

**Última atualização:** 2026-02-26

## 🚀 Iniciar Conversa com o Agente

### Opção 1: Web Chat (Mais Fácil)

Abra no navegador (sempre incluir o token na URL!):
```
http://127.0.0.1:18789/chat?session=agent%3Amain%3Amain&token=DAzqHHHuze75ix8NiwhKjQswnf0-6Bs1uyqBAofa1es
```

Ou a UI de controle:
```
http://127.0.0.1:18789/#token=DAzqHHHuze75ix8NiwhKjQswnf0-6Bs1uyqBAofa1es
```

**Vantagens:**
- Interface visual
- Histórico de conversa
- Fácil de usar

### Opção 2: Telegram

1. **Bot já configurado:** @genaubbt_bot
2. Envie uma mensagem para o bot
3. O agente responderá automaticamente

**Comandos úteis:**
- `/model grok` - Usar Grok 4.1 (SuperGrok)
- `/model sonnet` - Usar Claude Sonnet 4.5
- `/model gpt4o` - Usar GPT-4o

### Opção 3: WhatsApp

1. **Número:** +554187607512
2. Já está linkado e funcionando
3. Envie mensagens normalmente

### Opção 4: Discord

**Status:** Plugin habilitado, mas precisa configurar bot token

Para configurar:
```bash
openclaw config set channels.discord.botToken "SEU_BOT_TOKEN"
openclaw gateway restart
```

### Opção 5: TUI (Terminal)

```bash
openclaw tui
```

Interface de terminal interativa.

## 📋 Comandos Úteis

### Verificar Status

```bash
# Status do gateway
openclaw gateway health

# Status dos modelos
openclaw models status

# Listar modelos disponíveis
openclaw models list
```

### Reiniciar Gateway

```bash
openclaw gateway restart
```

### Trocar Modelo no Chat

Durante uma conversa, você pode usar:
- `/model grok` - Grok 4.1 (SuperGrok) - PRIMARY
- `/model sonnet` - Claude Sonnet 4.5
- `/model gpt4o` - GPT-4o (grátis)

## 🎯 Exemplos de Uso

### 1. Análise de Mercados Polymarket

```
Analise os mercados trending no Polymarket, calcule edge em 3 crypto Up/Down, 
e proponha o primeiro paper trade com $1 simulado
```

### 2. Executar Ações

O agente pode:
- Ler arquivos do workspace
- Executar comandos (com permissão)
- Usar skills (PolyWhale, LatencyNinja, etc.)
- Analisar dados
- Fazer trades simulados (dry-run)

### 3. Trabalhar com Código

```
Analise o arquivo scripts/polymarket-exec.py e sugira melhorias de performance
```

## 🔧 Configuração Atual

### Modelos Configurados

- **Primary:** `xai/grok-4.1` (SuperGrok)
- **Fallback 1:** `anthropic/claude-sonnet-4-5` (Claude)
- **Fallback 2:** `openai/gpt-4o` (GPT-4o via OAuth)

### Skills Ativos

- ✅ **polyclaw** - Trading Polymarket (ClawHub)
- ✅ **polywhale** - Análise de mercados
- ✅ **latencyninja** - Otimização de latência
- ✅ **configdash** - Dashboard de configuração
- ✅ **polymarket-exec** - Executor direto (dry-run)

### Canais Configurados

- ✅ **Telegram** - @genaubbt_bot (funcionando)
- ✅ **WhatsApp** - +554187607512 (linkado)
- ⚠️ **Discord** - Plugin habilitado, precisa bot token
- ✅ **Web Chat** - http://127.0.0.1:18789/chat?token=DAzqHHHuze75ix8NiwhKjQswnf0-6Bs1uyqBAofa1es

## 🛠️ Troubleshooting

> **IMPORTANTE:** Ler `INFRASTRUCTURE.md` para todos os procedimentos detalhados.

### Gateway não responde

```bash
openclaw gateway restart
openclaw gateway health
```

### "pairing required" no Web Chat

1. Garantir que o token na URL está correto (ver URLs acima)
2. Verificar tokens: `plutil -p ~/Library/LaunchAgents/ai.openclaw.gateway.plist | grep TOKEN`
3. Listar devices pendentes: `openclaw devices list`
4. Aprovar: `openclaw devices approve <REQUEST_ID>`
5. Se "connect failed": limpar localStorage do browser e repetir

### Modelo não funciona

Verifique se as API keys estão configuradas:
```bash
openclaw models status
```

### Executor não inicia

```bash
# Verificar se está rodando
lsof -i :8789

# Iniciar executor
bash scripts/start-executor.sh
```

### Discord não funciona

1. Crie um bot no Discord Developer Portal
2. Copie o bot token
3. Configure:
   ```bash
   openclaw config set channels.discord.botToken "SEU_TOKEN"
   openclaw gateway restart
   ```

## 📝 Notas Importantes

1. **Workspace:** `/Users/genautech/clawd`
2. **Gateway Port:** 18789
3. **Executor Port:** 8789 (dry-run mode)
4. **Logs:** `~/.openclaw/logs/` e `logs/polymarket-exec.log`

## 🎉 Pronto para Usar!

Agora você pode começar a conversar com o agente via qualquer canal configurado. 
O agente está pronto para executar ações, analisar dados, e trabalhar com o projeto!
