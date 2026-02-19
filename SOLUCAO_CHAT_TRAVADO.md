# Solução para Chat Travado - OpenClaw

## Problema Identificado

O chat está mostrando erros de **Content Security Policy (CSP)** bloqueando fontes do Google Fonts. Embora isso cause avisos no console, **não deveria travar o chat completamente**.

## Análise

O CSP atual do OpenClaw é:
```
Content-Security-Policy: default-src 'self'; style-src 'self' 'unsafe-inline'; font-src 'self'
```

Isso bloqueia:
- ✅ Fontes do Google (`https://fonts.googleapis.com`)
- ❌ Mas permite JavaScript local (`script-src 'self'`)
- ❌ E permite WebSocket (`connect-src 'self' ws: wss:`)

## Possíveis Causas do Travamento

1. **JavaScript não executa** - Verifique console do navegador (F12)
2. **WebSocket não conecta** - Verifique conexão WebSocket
3. **API não responde** - Verifique se `/api/sessions` responde
4. **React não renderiza** - Verifique se há erros no console

## Soluções

### Solução 1: Verificar Console do Navegador

1. Abra o chat: `http://127.0.0.1:18789/chat?session=agent:main:main`
2. Pressione **F12** (ou Cmd+Option+I no Mac)
3. Vá para a aba **Console**
4. Procure por erros em vermelho
5. Anote os erros e me informe

### Solução 2: Testar WebSocket Manualmente

Abra o console do navegador e execute:

```javascript
const ws = new WebSocket('ws://127.0.0.1:18789/ws?token=87969d5b456a17e15c44341a10f3b1020c2cc7db3ac3465c02a32de473777a09');
ws.onopen = () => console.log('WebSocket conectado!');
ws.onerror = (e) => console.error('WebSocket erro:', e);
ws.onclose = (e) => console.log('WebSocket fechado:', e.code, e.reason);
```

### Solução 3: Verificar se o Gateway Está Funcionando

```bash
openclaw gateway health
```

Deve mostrar:
```
OK
Telegram: ok
WhatsApp: linked
```

### Solução 4: Reiniciar Gateway

```bash
openclaw gateway restart
```

Aguarde 5 segundos e tente novamente.

## Sobre o Erro de CSP

O erro de CSP sobre fontes do Google é **apenas um aviso visual**. O chat deve funcionar mesmo com esse aviso. Se o chat está realmente travado, o problema provavelmente é outro.

## Próximos Passos

1. Verifique o console do navegador para erros JavaScript
2. Teste o WebSocket manualmente (código acima)
3. Me informe quais erros aparecem no console
4. Tente enviar uma mensagem e veja se há resposta

## Nota

O OpenClaw não permite configurar CSP diretamente via `openclaw config`. O CSP é definido internamente pelo gateway. Os avisos sobre fontes não devem impedir o funcionamento do chat.
