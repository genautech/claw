# Como Enviar Mensagens para o Agente

## Opção 1: Web Channel (Recomendado - Funciona Imediatamente)

Acesse diretamente no navegador:

```
http://127.0.0.1:18789/chat?session=agent%3Amain%3Amain&token=87969d5b456a17e15c44341a10f3b1020c2cc7db3ac3465c02a32de473777a09
```

**Vantagens:**
- ✅ Funciona imediatamente, sem configuração
- ✅ Não precisa fazer pairing
- ✅ Interface web completa
- ✅ Acesso local seguro

## Opção 2: Telegram (@genaubbt_bot)

**Status atual:** Configurado, mas requer pairing

### Para usar Telegram sem pairing:

Mude a política de DM para "open":

```bash
openclaw config set channels.telegram.dmPolicy open
openclaw config set channels.telegram.allowFrom '["*"]'
openclaw gateway restart
```

Depois disso, você pode enviar mensagens diretamente para `@genaubbt_bot` no Telegram.

## Opção 3: WhatsApp

**Status atual:** Linkado, mas requer pairing

### Para usar WhatsApp sem pairing:

```bash
openclaw config set channels.whatsapp.dmPolicy open
openclaw config set channels.whatsapp.allowFrom '["*"]'
openclaw gateway restart
```

Depois disso, você pode enviar mensagens diretamente para o número do bot no WhatsApp.

## Opção 4: Manter Pairing (Mais Seguro)

Se preferir manter a segurança do pairing:

1. Envie uma mensagem para o bot (Telegram ou WhatsApp)
2. Você receberá um código de pairing
3. Aprove o código:

```bash
# Ver códigos pendentes
openclaw pairing list telegram
openclaw pairing list whatsapp

# Aprovar um código
openclaw pairing approve telegram <CODIGO>
openclaw pairing approve whatsapp <CODIGO>
```

## Recomendação

Para uso local/desenvolvimento: **Use o Web Channel** (Opção 1) - é o mais simples e não requer mudanças de configuração.

Para uso em produção: Configure `dmPolicy: "open"` apenas se confiar no ambiente, ou use pairing para segurança.
