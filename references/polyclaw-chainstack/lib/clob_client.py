"""CLOB trading client wrapper.

Wraps py-clob-client for order execution with proxy support.
Includes retry logic for Cloudflare blocks when using rotating proxies.
"""

import os
import time
from typing import Optional

import httpx

# Max retries for Cloudflare blocks (with rotating proxy, each retry gets new IP)
CLOB_MAX_RETRIES = int(os.environ.get("CLOB_MAX_RETRIES", "5"))
CLOB_HTTP_TIMEOUT = float(os.environ.get("CLOB_HTTP_TIMEOUT", "30"))


class ClobClientWrapper:
    """Wrapper around py-clob-client for trading."""

    def __init__(self, private_key: str, address: str, api_key: Optional[str] = None, api_secret: Optional[str] = None, api_passphrase: Optional[str] = None):
        self.private_key = private_key
        self.address = address
        self.api_key = api_key or os.environ.get("POLYMARKET_API_KEY")
        self.api_secret = api_secret or os.environ.get("POLYMARKET_API_SECRET")
        self.api_passphrase = api_passphrase or os.environ.get("POLYMARKET_API_PASSPHRASE")
        self._client = None
        self._creds = None

    def _refresh_http_client(self):
        """Create a fresh HTTP client (for IP rotation with proxies)."""
        import py_clob_client.http_helpers.helpers as clob_helpers

        proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")
        if proxy:
            # Close old client if exists
            if hasattr(clob_helpers, '_http_client') and clob_helpers._http_client:
                try:
                    clob_helpers._http_client.close()
                except Exception:
                    pass
            # Create fresh client (gets new IP with rotating proxies)
            clob_helpers._http_client = httpx.Client(
                http2=True, proxy=proxy, timeout=CLOB_HTTP_TIMEOUT
            )

    def _init_client(self):
        """Initialize CLOB client with optional proxy support."""
        try:
            from py_clob_client.client import ClobClient
            import py_clob_client.http_helpers.helpers as clob_helpers
        except ImportError:
            raise ImportError(
                "py-clob-client not installed. Run: pip install py-clob-client"
            )

        # Configure proxy if available
        proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")
        if proxy:
            clob_helpers._http_client = httpx.Client(
                http2=True, proxy=proxy, timeout=CLOB_HTTP_TIMEOUT
            )

        # Initialize client
        self._client = ClobClient(
            "https://clob.polymarket.com",
            key=self.private_key,
            chain_id=137,
            signature_type=0,
            funder=self.address,
        )

        # Set up API credentials
        if self.api_key and self.api_secret and self.api_passphrase:
            # Use provided API credentials
            try:
                from py_clob_client.utilities.helpers import ApiCreds
                self._creds = ApiCreds(
                    api_key=self.api_key,
                    api_secret=self.api_secret,
                    api_passphrase=self.api_passphrase
                )
                self._client.set_api_creds(self._creds)
            except (ImportError, AttributeError):
                # Fallback: try to create creds object manually
                try:
                    # Create a dict-like structure that py-clob-client expects
                    self._creds = {
                        "apiKey": self.api_key,
                        "apiSecret": self.api_secret,
                        "apiPassphrase": self.api_passphrase
                    }
                    self._client.set_api_creds(self._creds)
                except Exception:
                    # If manual creation fails, log warning and use auto-derive
                    import warnings
                    warnings.warn("Could not set provided API credentials, falling back to auto-derive")
                    self._creds = self._client.create_or_derive_api_creds()
                    self._client.set_api_creds(self._creds)
        else:
            # Fallback to auto-create/derive if credentials not provided
            self._creds = self._client.create_or_derive_api_creds()
            self._client.set_api_creds(self._creds)

    @property
    def client(self):
        """Get or initialize CLOB client."""
        if self._client is None:
            self._init_client()
        return self._client

    def _is_cloudflare_block(self, error_msg: str) -> bool:
        """Check if error is a Cloudflare block."""
        return "403" in error_msg and ("cloudflare" in error_msg.lower() or "blocked" in error_msg.lower())

    def sell_fok(
        self,
        token_id: str,
        amount: float,
        price: float,
    ) -> tuple[Optional[str], bool, Optional[str]]:
        """
        Sell tokens via CLOB using FOK (Fill or Kill) order.

        Args:
            token_id: Token ID to sell
            amount: Amount of tokens to sell
            price: Current market price (will sell 10% below)

        Returns:
            Tuple of (order_id, filled, error_message)
        """
        from py_clob_client.clob_types import OrderArgs, OrderType
        from py_clob_client.order_builder.constants import SELL

        # Set low price to match any buy orders (market sell)
        sell_price = round(max(price * 0.90, 0.01), 2)

        last_error = None
        proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")

        for attempt in range(CLOB_MAX_RETRIES):
            try:
                # Refresh HTTP client for new IP (only if using proxy and retrying)
                if attempt > 0 and proxy:
                    print(f"  Retrying CLOB sell (attempt {attempt + 1}/{CLOB_MAX_RETRIES})...")
                    self._refresh_http_client()
                    time.sleep(1)  # Brief pause between retries

                order = self.client.create_order(
                    OrderArgs(
                        token_id=token_id,
                        price=sell_price,
                        size=amount,
                        side=SELL,
                    )
                )
                result = self.client.post_order(order, OrderType.FOK)
                order_id = result.get("orderID", str(result)[:40])
                return order_id, True, None

            except Exception as e:
                last_error = str(e)

                # Only retry on Cloudflare blocks when using a proxy
                if self._is_cloudflare_block(last_error) and proxy:
                    continue  # Try again with new IP

                # Non-retryable error
                break

        # All retries exhausted or non-retryable error
        if self._is_cloudflare_block(last_error):
            error_msg = (
                "IP blocked by Cloudflare. Your split succeeded - you have the tokens. "
                "Sell manually at polymarket.com or try with HTTPS_PROXY env var."
            )
        elif "no match" in last_error.lower() or "insufficient" in last_error.lower():
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
        """
        Place GTC (Good Till Cancelled) buy order.

        Args:
            token_id: Token ID to buy
            amount: Amount of tokens to buy
            price: Price per token

        Returns:
            Tuple of (order_id, error_message)
        """
        from py_clob_client.clob_types import OrderArgs, OrderType
        from py_clob_client.order_builder.constants import BUY

        proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")
        last_error = None

        for attempt in range(CLOB_MAX_RETRIES):
            try:
                if attempt > 0 and proxy:
                    self._refresh_http_client()
                    time.sleep(1)

                order = self.client.create_order(
                    OrderArgs(
                        token_id=token_id,
                        price=round(price, 2),
                        size=amount,
                        side=BUY,
                    )
                )
                result = self.client.post_order(order, OrderType.GTC)
                order_id = result.get("orderID", str(result)[:40])
                return order_id, None
            except Exception as e:
                last_error = str(e)
                if self._is_cloudflare_block(last_error) and proxy:
                    continue
                break

        return None, last_error

    def get_order_book(self, token_id: str) -> dict:
        """Get order book for a token."""
        return self.client.get_order_book(token_id)

    def get_orders(self) -> list:
        """Get all open orders."""
        return self.client.get_orders()

    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order."""
        try:
            self.client.cancel(order_id)
            return True
        except Exception:
            return False
