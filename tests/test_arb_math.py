"""Deterministic unit tests for the arbitrage math in scripts/agent_arb.py.

Run: python3 -m pytest tests/test_arb_math.py -v
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import agent_arb  # noqa: E402


def test_best_ask_picks_lowest_regardless_of_order():
    assert agent_arb.best_ask_from_book([{"price": "0.52"}, {"price": "0.51"}]) == 0.51
    assert agent_arb.best_ask_from_book([{"price": "0.40"}, {"price": "0.55"}]) == 0.40


def test_best_ask_handles_empty_and_garbage():
    assert agent_arb.best_ask_from_book([]) is None
    assert agent_arb.best_ask_from_book(None) is None
    assert agent_arb.best_ask_from_book([{"nope": 1}, {"price": "x"}]) is None


def test_binary_profitable_arb():
    # 0.48 + 0.49 = 0.97 -> ~0.93% net after 2% fee + gas
    a = agent_arb.compute_arb([0.48, 0.49], size_usd=100)
    assert a is not None
    assert a["sum_ask"] == 0.97
    assert a["n_outcomes"] == 2
    assert a["net_usd"] > 0
    assert a["profitable"] is True


def test_binary_sum_exactly_one_is_not_profitable():
    a = agent_arb.compute_arb([0.50, 0.50], size_usd=100)
    assert a["net_usd"] < 0
    assert a["profitable"] is False


def test_sum_over_one_not_profitable():
    a = agent_arb.compute_arb([0.55, 0.50], size_usd=100)
    assert a["sum_ask"] == 1.05
    assert a["profitable"] is False


def test_multi_outcome_negrisk_profitable():
    a = agent_arb.compute_arb([0.30, 0.30, 0.30], size_usd=100)
    assert a["n_outcomes"] == 3
    assert a["sum_ask"] == 0.90
    assert a["net_usd"] > 0
    assert a["profitable"] is True


def test_edge_below_buffer_is_rejected():
    # 0.488 + 0.488 = 0.976 -> ~0.31% net, below the 0.5% default buffer
    a = agent_arb.compute_arb([0.488, 0.488], size_usd=100)
    assert a["net_pct"] < agent_arb.EDGE_BUFFER_PCT
    assert a["profitable"] is False


def test_compute_arb_invalid_inputs():
    assert agent_arb.compute_arb([], size_usd=100) is None
    assert agent_arb.compute_arb([0.5, None], size_usd=100) is None
    assert agent_arb.compute_arb([0.5, 0.4], size_usd=0) is None


def test_fractional_kelly_sizing():
    assert agent_arb.fractional_kelly_size(0.0) == 0.0
    assert agent_arb.fractional_kelly_size(-0.1) == 0.0
    # positive edge -> min(max_position, capital*fraction)
    size = agent_arb.fractional_kelly_size(0.05, capital=1000, fraction=0.25, max_position=50)
    assert size == 50.0
    size2 = agent_arb.fractional_kelly_size(0.05, capital=100, fraction=0.25, max_position=50)
    assert size2 == 25.0
