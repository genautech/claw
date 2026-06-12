#!/usr/bin/env python3
"""
ArbReport - paper-trading metrics for the arbitrage agent + go-live gate check.

Reads data/arb_opportunities.jsonl and prints a summary:
- number of opportunities (by type)
- average / best net edge
- cumulative paper PnL
- whether the go-live criteria are met

Run: python3 scripts/arb_report.py
"""

import json
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.absolute()
OPP_FILE = PROJECT_ROOT / "data" / "arb_opportunities.jsonl"

# Go-live criteria (paper must clear these before enabling LIVE_TRADING).
GOLIVE_MIN_OPPORTUNITIES = int(os.environ.get("GOLIVE_MIN_OPPORTUNITIES", "20"))
GOLIVE_MIN_PAPER_PNL = float(os.environ.get("GOLIVE_MIN_PAPER_PNL", "0"))


def load_records(path: Path) -> list[dict]:
    if not path.exists():
        return []
    records = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def summarize(records: list[dict]) -> dict:
    opps = [r for r in records if r.get("type") in ("binary_sum_to_one", "negrisk_multi_outcome")]
    by_type: dict[str, int] = {}
    for o in opps:
        by_type[o["type"]] = by_type.get(o["type"], 0) + 1

    edges = [o.get("net_edge_pct", 0.0) for o in opps]
    paper_pnls = [o.get("paper_pnl", 0.0) for o in opps]
    cumulative = max((o.get("cumulative_paper_pnl", 0.0) for o in opps), default=0.0)

    return {
        "opportunities": len(opps),
        "by_type": by_type,
        "avg_net_edge_pct": round(sum(edges) / len(edges), 5) if edges else 0.0,
        "best_net_edge_pct": round(max(edges), 5) if edges else 0.0,
        "total_paper_pnl": round(sum(paper_pnls), 4),
        "cumulative_paper_pnl": round(cumulative, 4),
        "sessions": len([r for r in records if r.get("type") == "arb_session_summary"]),
    }


def golive_ready(summary: dict) -> tuple[bool, str]:
    if summary["opportunities"] < GOLIVE_MIN_OPPORTUNITIES:
        return False, (
            f"Need >= {GOLIVE_MIN_OPPORTUNITIES} paper opportunities "
            f"(have {summary['opportunities']})"
        )
    if summary["total_paper_pnl"] <= GOLIVE_MIN_PAPER_PNL:
        return False, (
            f"Paper PnL ${summary['total_paper_pnl']} must exceed "
            f"${GOLIVE_MIN_PAPER_PNL}"
        )
    return True, "Paper criteria met - safe to evaluate enabling LIVE_TRADING."


def main() -> None:
    records = load_records(OPP_FILE)
    summary = summarize(records)
    ready, reason = golive_ready(summary)

    print("=" * 60)
    print("ARB PAPER REPORT")
    print("=" * 60)
    print(f"  File:                 {OPP_FILE}")
    print(f"  Opportunities:        {summary['opportunities']}")
    print(f"  By type:              {summary['by_type']}")
    print(f"  Avg net edge:         {summary['avg_net_edge_pct'] * 100:.3f}%")
    print(f"  Best net edge:        {summary['best_net_edge_pct'] * 100:.3f}%")
    print(f"  Total paper PnL:      ${summary['total_paper_pnl']}")
    print(f"  Cumulative paper PnL: ${summary['cumulative_paper_pnl']}")
    print(f"  Sessions logged:      {summary['sessions']}")
    print("-" * 60)
    print(f"  GO-LIVE GATE:         {'READY' if ready else 'BLOCKED'} - {reason}")
    print("=" * 60)


if __name__ == "__main__":
    main()
