"""CLOB trading client wrapper.

Wraps py_clob_client_v2 for order execution with proxy support.
Includes retry logic for Cloudflare blocks when using rotating proxies.
"""

import os
import time
from typing import Optional

import httpx

CLOB_MAX_RETRIES = int(os.environ.get("CLOB_MAX_RETRIES", "5"))
CLOB_HTTP_TIMEOUT = float(os.environ.get("CLOB_HTTP_TIMEOUT", "30"))


class ClobClientWrapper:
    """Wrapper around py_clob_client_v2 for trading."""

    def __init__(self, private_key: str, address: str, api_key: Optional[str] = None, api_secret: Optional[str] = None, api_passphrase: Optional[str] = None, proxy_address: Optional[str] = None):
        self.private_key = private_key
        self.address = address
        self.proxy_address = proxy_address or os.environ.get("POLYMARKET_PROXY_ADDRESS")
        self.api_key = api_key or os.environ.get("POLYMARKET_API_KEY")
        self.api_secret = api_secret or os.environ.get("POLYMARKET_API_SECRET")
        self.api_passphrase = api_passphrase or os.environ.get("POLYMARKET_API_PASSPHRASE")
        self._client = None

    def _init_client(self):
        """Initialize CLOB V2 client."""
        from py_clob_client_v2 import ApiCreds, ClobClient

        sig_type = 2 if self.proxy_address else 0
        funder = self.proxy_address if self.proxy_address else self.address

        creds = None
        if self.api_key and self.api_secret and self.api_passphrase:
            creds = ApiCreds(
                api_key=self.api_key,
                api_secret=self.api_secret,
                api_passphrase=self.api_passphrase,
            )

        self._client = ClobClient(
            host="https://clob.polymarket.com",
            chain_id=137,
            key=self.private_key,
            creds=creds,
            signature_type=sig_type,
            funder=funder,
        )

        if creds is None:
            derived = self._client.create_or_derive_api_key()
            self._client.set_api_creds(derived)

    @property
    def client(self):
        if self._client is None:
            self._init_client()
        return self._client

    def _is_cloudflare_block(self, error_msg: str) -> bool:
        return "403" in error_msg and ("cloudflare" in error_msg.lower() or "blocked" in error_msg.lower())

    def sell_fok(
        self,
        token_id: str,
        amount: float,
        price: float,
    ) -> tuple[Optional[str], bool, Optional[str]]:
        """Sell tokens via CLOB using FOK order."""
        from py_clob_client_v2 import OrderArgs, OrderType, PartialCreateOrderOptions, Side

        sell_price = round(max(price * 0.90, 0.01), 2)
        last_error = None

        for attempt in range(CLOB_MAX_RETRIES):
            try:
                if attempt > 0:
                    time.sleep(1)

                result = self.client.create_and_post_order(
                    order_args=OrderArgs(
                        token_id=token_id,
                        price=sell_price,
                        size=amount,
                        side=Side.SELL,
                    ),
                    options=PartialCreateOrderOptions(tick_size="0.01"),
                    order_type=OrderType.FOK,
                )

                if result.get("success"):
                    order_id = result.get("orderID", str(result)[:40])
                    return order_id, True, None
                else:
                    last_error = result.get("errorMsg", str(result))
                    break

            except Exception as e:
                last_error = str(e)
                if self._is_cloudflare_block(last_error):
                    continue
                break

        if last_error and ("no match" in last_error.lower() or "insufficient" in last_error.lower()):
            error_msg = f"No liquidity at ${sell_price:.2f} - tokens kept, sell manually"
        else:
            error_msg = last_error

        return None, False, error_msg

    def buy_gtc(
        self,
        token_id: str,
        amount: float,
        price: float,
    ) -> tuple[Optional[str], Optional[str]]:
        """Place GTC buy order."""
        from py_clob_client_v2 import OrderArgs, OrderType, PartialCreateOrderOptions, Side

        last_error = None

        for attempt in range(CLOB_MAX_RETRIES):
            try:
                if attempt > 0:
                    time.sleep(1)

                result = self.client.create_and_post_order(
                    order_args=OrderArgs(
                        token_id=token_id,
                        price=round(price, 2),
                        size=amount,
                        side=Side.BUY,
                    ),
                    options=PartialCreateOrderOptions(tick_size="0.01"),
                    order_type=OrderType.GTC,
                )

                if result.get("success"):
                    order_id = result.get("orderID", str(result)[:40])
                    return order_id, None
                else:
                    last_error = result.get("errorMsg", str(result))
                    break

            except Exception as e:
                last_error = str(e)
                if self._is_cloudflare_block(last_error):
                    continue
                break

        return None, last_error

    def sell_gtc(
        self,
        token_id: str,
        amount: float,
        price: float,
    ) -> tuple[Optional[str], Optional[str]]:
        """Place GTC sell order."""
        from py_clob_client_v2 import OrderArgs, OrderType, PartialCreateOrderOptions, Side

        last_error = None
        for attempt in range(CLOB_MAX_RETRIES):
            try:
                if attempt > 0:
                    time.sleep(1)
                result = self.client.create_and_post_order(
                    order_args=OrderArgs(
                        token_id=token_id,
                        price=round(max(price, 0.01), 2),
                        size=amount,
                        side=Side.SELL,
                    ),
                    options=PartialCreateOrderOptions(tick_size="0.01"),
                    order_type=OrderType.GTC,
                )
                if result.get("success"):
                    order_id = result.get("orderID", str(result)[:40])
                    return order_id, None
                last_error = result.get("errorMsg", str(result))
                break
            except Exception as e:
                last_error = str(e)
                if self._is_cloudflare_block(last_error):
                    continue
                break
        return None, last_error

    def get_order_book(self, token_id: str) -> dict:
        return self.client.get_order_book(token_id)

    def get_orders(self) -> list:
        return self.client.get_open_orders()

    def cancel_order(self, order_id: str) -> bool:
        try:
            self.client.cancel_order(order_id)
            return True
        except Exception:
            return False
