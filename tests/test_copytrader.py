"""Offline unit tests for scripts/agent_copytrader.py (no network).

Run: python3 -m pytest tests/test_copytrader.py -v
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import agent_copytrader as ct  # noqa: E402


def test_trade_usd():
    assert ct.trade_usd({"size": 5, "price": 0.41}) == 5 * 0.41
    assert ct.trade_usd({"size": "bad"}) == 0.0
    assert ct.trade_usd({}) == 0.0


def test_trade_id_prefers_tx_hash():
    assert ct.trade_id({"transactionHash": "0xabc"}) == "0xabc"
    tid = ct.trade_id({"proxyWallet": "0xW", "asset": "T", "timestamp": 123})
    assert tid == "0xW:T:123"


def test_should_copy_filters_side_and_dust():
    assert ct.should_copy({"side": "BUY", "size": 100, "price": 0.5}) is True
    assert ct.should_copy({"side": "SELL", "size": 100, "price": 0.5}) is False
    assert ct.should_copy({"side": "BUY", "size": 1, "price": 0.5}) is False  # $0.50 < $5


def test_mirror_size_fraction_and_cap():
    assert ct.mirror_size(100, fraction=0.10, max_position=25) == 10.0
    assert ct.mirror_size(500, fraction=0.10, max_position=25) == 25.0  # capped
    assert ct.mirror_size(0) == 0.0


def test_score_wallet_roi_and_winrate():
    positions = [
        {"totalBought": 100, "cashPnl": 20, "realizedPnl": 20},
        {"totalBought": 100, "cashPnl": -10, "realizedPnl": -10},
    ]
    s = ct.score_wallet(positions)
    assert s["invested_usd"] == 200
    assert s["cash_pnl_usd"] == 10
    assert abs(s["roi"] - 0.05) < 1e-9
    assert abs(s["winrate"] - 0.5) < 1e-9
    assert s["n_positions"] == 2


def test_score_wallet_empty():
    s = ct.score_wallet([])
    assert s["roi"] == 0.0
    assert s["winrate"] == 0.0
    assert s["n_positions"] == 0


def test_rank_wallets_orders_by_score():
    wp = {
        "0xLow": [{"totalBought": 100, "cashPnl": 5}],     # roi 0.05
        "0xHigh": [{"totalBought": 100, "cashPnl": 50}],   # roi 0.50
    }
    ranked = ct.rank_wallets(wp)
    assert ranked[0]["wallet"] == "0xHigh"
    assert ranked[1]["wallet"] == "0xLow"
    assert ranked[0]["score"] > ranked[1]["score"]
