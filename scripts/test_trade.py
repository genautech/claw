#!/usr/bin/env python3
"""
Teste direto de trade no Polymarket — sem FastAPI.
Lê credenciais do openclaw.json, verifica saldo e coloca ordem.
"""
import json, os, sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "references" / "polyclaw-chainstack"))

# Carregar credenciais
cfg_path = os.path.expanduser("~/.openclaw/openclaw.json")
cfg = json.loads(open(cfg_path).read())
env = cfg["skills"]["entries"]["polymarket-exec"]["env"]

PK               = env["POLYMARKET_PK"]
ADDRESS          = env["POLYMARKET_ADDRESS"]
PROXY_ADDRESS    = env.get("POLYMARKET_PROXY_ADDRESS", "")
API_KEY          = env.get("POLYMARKET_API_KEY", "")
API_SECRET       = env.get("POLYMARKET_API_SECRET", "")
API_PASSPHRASE   = env.get("POLYMARKET_API_PASSPHRASE", "")

print(f"Signer:  {ADDRESS}")
print(f"Proxy:   {PROXY_ADDRESS}")
print(f"API key: {API_KEY[:20]}...")

from lib.clob_client import ClobClientWrapper
from py_clob_client_v2.clob_types import BalanceAllowanceParams

client = ClobClientWrapper(
    PK, ADDRESS,
    api_key=API_KEY,
    api_secret=API_SECRET,
    api_passphrase=API_PASSPHRASE,
    proxy_address=PROXY_ADDRESS,
)

print("\n=== SALDO ===")
try:
    bal = client.client.get_balance_allowance(BalanceAllowanceParams(asset_type="COLLATERAL"))
    usdc = float(bal.get("balance", 0)) / 1e6
    print(f"USDC (collateral): ${usdc:.4f}")
    print(f"Raw response: {bal}")
except Exception as e:
    print(f"Erro saldo: {e}")

print("\n=== ORDENS ABERTAS ===")
try:
    orders = client.get_orders()
    print(f"Ordens: {len(orders) if isinstance(orders, list) else orders}")
except Exception as e:
    print(f"Erro ordens: {e}")

# Market ID para "Will United States win on 2026-07-01?"
CONDITION_ID = "0xe9d96f957f3f5e4ffa0e920087edf967c4cc353e9d1ad0c2d7ae928b32b61cb0"
# YES token ID
YES_TOKEN = "4633569295739345295929299496370398790000429459208303788658430774702495448690"

DRY_RUN = "--dry" in sys.argv or True  # dry por padrão
if "--live" in sys.argv:
    DRY_RUN = False

SIZE_USD = 5.0  # mínimo do mercado é 5 USDC
PRICE = 0.87    # bestAsk atual
TOKEN_AMOUNT = SIZE_USD / PRICE

print(f"\n=== ORDEM TEST ===")
print(f"Mercado: Will United States win on 2026-07-01?")
print(f"Token:   YES ({YES_TOKEN[:20]}...)")
print(f"Tamanho: ${SIZE_USD} → {TOKEN_AMOUNT:.2f} tokens @ ${PRICE}")
print(f"Dry run: {DRY_RUN}")

if not DRY_RUN:
    print("\nExecutando ordem REAL...")
    order_id, error = client.buy_gtc(YES_TOKEN, TOKEN_AMOUNT, PRICE)
    if error:
        print(f"ERRO: {error}")
    else:
        print(f"Ordem executada: {order_id}")
else:
    print("\n[DRY RUN] Ordem não executada. Use --live para executar de verdade.")
