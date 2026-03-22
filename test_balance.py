import asyncio
import os
import sys
import json
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path('.').absolute()
sys.path.insert(0, str(PROJECT_ROOT / "references" / "polyclaw-chainstack"))

from dotenv import load_dotenv

env_paths = [
    PROJECT_ROOT / ".env",
    PROJECT_ROOT / ".env.local",
    PROJECT_ROOT / "dashboard-next" / ".env.local",
    PROJECT_ROOT / "mc-docker" / "backend" / ".env"
]
for p in env_paths:
    if p.exists():
        load_dotenv(p)

from lib.clob_client import ClobClientWrapper

async def main():
    pk = os.environ.get("POLYMARKET_PK") or os.environ.get("POLYCLAW_PRIVATE_KEY")
    addr = os.environ.get("POLYMARKET_ADDRESS")
    if not pk or not addr:
        print("No creds found")
        return
    
    wrapper = ClobClientWrapper(private_key=pk, address=addr)
    # The client might have a get_balance_allowance method
    from py_clob_client.clob_types import BalanceAllowanceParams
    
    res = wrapper.client.get_balance_allowance(BalanceAllowanceParams(asset_type="COLLATERAL"))
    print("Balance from clob:")
    print(res)

if __name__ == "__main__":
    asyncio.run(main())
