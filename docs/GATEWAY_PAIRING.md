# OpenClaw Gateway Device Pairing

If you see `pairing required` or `device_token_mismatch` when running `openclaw health` or when Mission Control fails with "missing scope: operator.admin", the gateway expects a **paired device** (CLI or browser), not a channel.

**Importante:** `openclaw pairing` é para **canais** (Telegram/WhatsApp/Discord — aprovar contatos em DM). O "pairing required" do gateway é **device pairing**: aprovar o próprio CLI ou o Mission Control como dispositivo. Comando para listar/aprovar dispositivos: `openclaw devices list` e `openclaw devices approve <requestId>` — mas esses comandos **só funcionam depois** que algum dispositivo já estiver aprovado (por isso o ciclo: precisa aprovar pela primeira vez pela Control UI no browser).

## "gateway token mismatch"

Se no log do gateway aparecer `unauthorized: gateway token mismatch (open the dashboard URL and paste the token in Control UI settings)`, significa que a Control UI (ou Cursor/Electron) abriu a URL **sem** o token. Sempre use o link **com** o token na query:

```
http://127.0.0.1:18789/?token=SEU_GATEWAY_TOKEN
```

O token está em `~/.openclaw/openclaw.json` → `gateway.auth.token`. Depois de `openclaw doctor --fix`, o arquivo pode ser sobrescrito; se o token tiver mudado, atualize também o "Gateway token" no Mission Control (Administration → Gateways → Edit).

## Se o gateway não sobe ou dá "another instance already listening"

```bash
openclaw gateway stop
# Aguarde alguns segundos, depois:
openclaw gateway start
```

## Corrigir avisos do Doctor (opcional)

```bash
openclaw doctor --fix
```

Isso remove chaves não reconhecidas (ex.: `channels.whatsapp.enabled`) e aplica mudanças sugeridas.

## Approve via script (pode falhar com "missing scope")

```bash
python3 scripts/approve-gateway-device.py
```

If the gateway rejects with "missing scope: operator.pairing", use the manual step below.

## Approve manually (Control UI) — jeito que funciona

1. Pegue o token do gateway:
   - Em `~/.openclaw/openclaw.json` → `gateway.auth.token`
   - Ou no Mission Control: Administration → Gateways → Local OpenClaw → editar e copiar "Gateway token"

2. Abra no **navegador** (Chrome/Safari):
   ```
   http://127.0.0.1:18789/?token=SEU_GATEWAY_TOKEN
   ```
   Exemplo: `http://127.0.0.1:18789/?token=DAzqHHHuze75ix8NiwhKjQswnf0-6Bs1uyqBAofa1es`

3. Na interface do OpenClaw (Control UI), procure **Devices** ou **Pairing** / **Dispositivos** e **aprovar** o pedido pendente (ex.: "cli" ou "gateway-client"). Só depois disso o `openclaw` na linha de comando consegue conectar.

4. Se precisar reiniciar o gateway:
   ```bash
   openclaw gateway stop
   openclaw gateway start
   ```

Depois que o device estiver aprovado, `openclaw health` e o sync do Mission Control passam a funcionar.
