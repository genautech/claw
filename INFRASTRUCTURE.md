# INFRASTRUCTURE.md — Referência Definitiva de Infraestrutura

> **Última atualização:** 2026-02-26
>
> Este arquivo é a **FONTE ÚNICA DE VERDADE** para todas as configurações, tokens, portas e procedimentos de inicialização do ClawdBot.
> **Agentes:** Leiam este arquivo antes de qualquer operação de infraestrutura.

---

## Arquitetura de Serviços

| Serviço | Porta | Tipo | Status |
|---------|-------|------|--------|
| OpenClaw Gateway | **18789** | LaunchAgent (macOS) | ✅ |
| Mission Control Frontend | **3001** | Docker (Next.js) | ✅ |
| Mission Control Backend | **8000** | Docker (FastAPI) | ✅ |
| Mission Control DB | **5432** | Docker (PostgreSQL 16) | ✅ |
| Mission Control Redis | **6379** | Docker (Redis 7) | ✅ |
| Mission Control Worker | — | Docker (RQ) | ✅ |
| PolyAgents Dashboard | **8888** | Streamlit | Manual |
| Polymarket Executor | **8789** | Python | Manual |
| Railway CLI | — | CLI (v4.30.5) | ✅ Instalado |

---

## 🔑 Tokens e Chaves

### Gateway Auth Token (ATIVO)
```
DAzqHHHuze75ix8NiwhKjQswnf0-6Bs1uyqBAofa1es
```
- Este é o token que o **LaunchAgent plist** usa (fonte de verdade para o gateway)
- Configura em: `~/.openclaw/openclaw.json` → `gateway.auth.token` e `gateway.remote.token`
- Usado nas URLs do Gateway UI e Web Chat
- **IMPORTANTE:** O token do config DEVE coincidir com o do plist. Se não coincidir, o health check na UI vai mostrar "Offline"

### Gateway Token no plist (NUNCA ALTERAR DIRETAMENTE)
```
DAzqHHHuze75ix8NiwhKjQswnf0-6Bs1uyqBAofa1es
```
- Local: `~/Library/LaunchAgents/ai.openclaw.gateway.plist` → `OPENCLAW_GATEWAY_TOKEN`
- Protegido por SIP — `openclaw gateway install --force` é a única forma de alterá-lo
- Se `install --force` falhar por SIP, use `osascript` admin para copiar um plist novo

### Mission Control LOCAL_AUTH_TOKEN
```
28564452b9b917626d3826260fa50fc0648905bb6e4fff85f4904bb248ee43ff
```
- Configura em: `mission-control/myenv.txt` → `LOCAL_AUTH_TOKEN`
- Usado para login no frontend (Self-Host Mode)

### Telegram Bot Token
```
8563095768:AAGv7_P-9s42UXqwQTGMxFXuCfIRBNz9Ne4
```
- Bot: @genaubbt_bot
- Configura em: `~/.openclaw/openclaw.json` → `channels.telegram.botToken`

---

## 📍 URLs de Acesso

| Serviço | URL |
|---------|-----|
| Gateway UI | `http://127.0.0.1:18789/#token=DAzqHHHuze75ix8NiwhKjQswnf0-6Bs1uyqBAofa1es` |
| Web Chat | `http://127.0.0.1:18789/chat?session=agent%3Amain%3Amain&token=DAzqHHHuze75ix8NiwhKjQswnf0-6Bs1uyqBAofa1es` |
| Mission Control | `http://localhost:3001` |
| MC API Docs | `http://localhost:8000/docs` |
| Dashboard | `http://localhost:8888` |

---

## 🚀 Procedimentos de Inicialização

### 1. Iniciar Gateway OpenClaw

```bash
# Verificar health
openclaw gateway health

# Se estiver parado:
openclaw gateway start

# Se precisar reiniciar:
openclaw gateway restart
```

### 2. Iniciar Mission Control (Docker)

```bash
cd /Users/genautech/clawd/mission-control

# O .env NÃO PODE ser lido via docker compose padrão (SIP do macOS)
# Use SEMPRE o --env-file apontando para /tmp/mc-env
cp myenv.txt /tmp/mc-env
docker compose --env-file /tmp/mc-env up -d

# Verificar containers
docker ps
```

### 3. Iniciar Dashboard (Streamlit)

```bash
cd /Users/genautech/clawd
streamlit run app.py --server.port 8888 --server.headless true
```

---

## ⚠️ Problemas Conhecidos e Soluções

### 1. macOS SIP / `com.apple.provenance`

O macOS protege arquivos baixados com `com.apple.provenance` xattr. Isso impede escrita em:
- `~/.openclaw/openclaw.json`
- `~/.openclaw/` (todo o diretório)
- `~/Library/LaunchAgents/ai.openclaw.gateway.plist`
- `mission-control/` (diretório clonado/baixado)

**Solução:** Usar `osascript` com permissões admin:
```bash
# Para copiar arquivo protegido
osascript -e 'do shell script "cp /tmp/meu_arquivo /caminho/protegido/" with administrator privileges'

# Para bootstrapar LaunchAgent
osascript -e 'do shell script "launchctl bootstrap gui/501 /Users/genautech/Library/LaunchAgents/ai.openclaw.gateway.plist" with administrator privileges'
```

**IMPORTANTE:** Escrever diretamente (via python, echo, tee) NÃO funciona. Sempre use a abordagem `osascript`.

### 2. "pairing required" no Web Chat

**Causa:** O browser Control UI precisa de **device pairing** aprovado pelo gateway. Cada browser/sessão tem um device ID único (armazenado no localStorage). Se o localStorage for limpo ou o device removido, uma nova aprovação é necessária.

**Solução definitiva:**
1. **Garantir que o token na URL está correto:**
   ```
   http://127.0.0.1:18789/chat?session=agent%3Amain%3Amain&token=DAzqHHHuze75ix8NiwhKjQswnf0-6Bs1uyqBAofa1es
   ```
2. **Garantir que o token do config coincide com o do plist:**
   ```bash
   # Verificar o token do plist (fonte de verdade)
   plutil -p ~/Library/LaunchAgents/ai.openclaw.gateway.plist | grep OPENCLAW_GATEWAY_TOKEN
   
   # Verificar o token do config
   cat ~/.openclaw/openclaw.json | python3 -c "import json,sys; c=json.load(sys.stdin); print(c['gateway']['auth']['token'])"
   
   # Se forem diferentes, atualizar o config para usar o token do plist
   ```
3. **Se "pairing required" aparecer:**
   ```bash
   # Listar pending devices
   openclaw devices list
   
   # Aprovar o device pendente (usar o Request ID da tabela)
   openclaw devices approve <REQUEST_ID>
   ```
4. **Se o device foi comprometido (connect failed / stale token):**
   - Limpar o localStorage do browser em `127.0.0.1:18789` (DevTools → Application → Storage → Clear)
   - Recarregar a página com o token na URL
   - Aprovar o novo pending device via CLI

### 3. Gateway "token missing" / "device token mismatch"

**Causa:** `~/.openclaw/openclaw.json` não tem `gateway.auth.token` e/ou `gateway.remote.token`, OU o token não coincide com o do plist.

**Solução:**
1. Verificar o token do plist: `plutil -p ~/Library/LaunchAgents/ai.openclaw.gateway.plist | grep TOKEN`
2. Atualizar o config para usar o MESMO token:
   ```bash
   python3 -c "
   import json
   with open('/Users/genautech/.openclaw/openclaw.json') as f:
       c = json.load(f)
   PLIST_TOKEN = 'DAzqHHHuze75ix8NiwhKjQswnf0-6Bs1uyqBAofa1es'
   c['gateway']['auth']['token'] = PLIST_TOKEN
   c['gateway']['remote']['token'] = PLIST_TOKEN
   with open('/tmp/openclaw_fixed.json', 'w') as f:
       json.dump(c, f, indent=2)
   "
   osascript -e 'do shell script "cp /tmp/openclaw_fixed.json /Users/genautech/.openclaw/openclaw.json" with administrator privileges'
   openclaw gateway restart
   ```

### 4. Backend ImportError `check_gateway_version_compatibility`

**Causa:** Volume mount em `compose.yml` sobrescreve `gateway_compat.py` mas o Docker image espera uma função com nome diferente.

**Solução:** Garantir que `gateway_compat.py` tem o alias no final:
```python
check_gateway_version_compatibility = check_gateway_runtime_compatibility
```

### 5. Docker Compose crash com `.env`

**Causa:** `docker compose` não consegue ler `.env` em diretórios protegidos por SIP.

**Solução:** Copiar o env para `/tmp` e usar `--env-file`:
```bash
cp mission-control/myenv.txt /tmp/mc-env
docker compose --env-file /tmp/mc-env up -d
```

---

## 📂 Arquivos de Configuração Importantes

| Arquivo | Descrição |
|---------|-----------|
| `~/.openclaw/openclaw.json` | Config principal do gateway (auth, models, channels, skills) |
| `~/Library/LaunchAgents/ai.openclaw.gateway.plist` | Plist do LaunchAgent (token, porta — FONTE DE VERDADE) |
| `config/openclaw-config.json5` | Template de referência (NÃO é o ativo) |
| `mission-control/myenv.txt` | Env canônico do MC (usar via `--env-file /tmp/mc-env`) |
| `mission-control/compose.yml` | Docker Compose do Mission Control |
| `docs/GATEWAY_PAIRING.md` | Guia de troubleshooting de device pairing |

---

## 🏗️ Estrutura do `~/.openclaw/openclaw.json` (campos críticos)

```json
{
  "gateway": {
    "port": 18789,
    "mode": "local",
    "bind": "auto",
    "controlUi": { "allowInsecureAuth": true },
    "auth": {
      "mode": "token",
      "token": "DAzqHHHuze75ix8NiwhKjQswnf0-6Bs1uyqBAofa1es"
    },
    "remote": {
      "token": "DAzqHHHuze75ix8NiwhKjQswnf0-6Bs1uyqBAofa1es"
    }
  }
}
```

**NUNCA** remover `gateway.auth.token` ou `gateway.remote.token`. Sem eles, o health check falha.
**SEMPRE** manter o token igual ao do plist (`plutil -p ~/Library/LaunchAgents/ai.openclaw.gateway.plist`).

---

## 🐳 Mission Control `.env` (Conteúdo Canônico — em `myenv.txt`)

```env
FRONTEND_PORT=3001
BACKEND_PORT=8000
POSTGRES_DB=mission_control
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_PORT=5432
CORS_ORIGINS=http://localhost:3001
DB_AUTO_MIGRATE=true
LOG_LEVEL=INFO
REQUEST_LOG_SLOW_MS=1000
AUTH_MODE=local
LOCAL_AUTH_TOKEN=28564452b9b917626d3826260fa50fc0648905bb6e4fff85f4904bb248ee43ff
NEXT_PUBLIC_API_URL=http://localhost:8000
```

> **NOTA:** O frontend fica na porta **3001** (não 3000) para evitar conflitos.
