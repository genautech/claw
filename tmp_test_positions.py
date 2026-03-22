import asyncio
import os
import sys
import httpx
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path('.').absolute()
sys.path.insert(0, str(PROJECT_ROOT / "references" / "polyclaw-chainstack"))

from dotenv import load_dotenv

env_paths = [
    PROJECT_ROOT / ".env",
    PROJECT_ROOT / ".env.local",
    PROJECT_ROOT / "dashboard-next" / ".env.local"
]
for p in env_paths:
    if p.exists():
        load_dotenv(p)
        print(f"Loaded {p}")

from lib.wallet_manager import WalletManager

async def main():
    wm = WalletManager()
    if not wm.is_unlocked:
        print("Wallet not unlocked")
        return
    
    address = wm.address
    print(f"Address: {address}")
    
    try:
        bals = wm.get_balances()
        print(f"Balances: {bals}")
    except Exception as e:
        print(f"Failed to get balances: {e}")

    url = f"https://data-api.polymarket.com/positions?user={address}"
    print(f"Fetching {url}")
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                print("Positions:", len(data))
                if data:
                    print(data[:2])
            else:
                print("Failed:", resp.status_code, resp.text)
    except Exception as e:
        print(f"Failed to get positions: {e}")

if __name__ == "__main__":
    asyncio.run(main())
