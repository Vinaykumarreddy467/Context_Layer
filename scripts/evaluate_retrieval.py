"""Evaluate Context Layer search against a hand-labeled JSON query set."""

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import context_layer as cl

SEARCH = {
    "text": cl.search_handoffs,
    "semantic": cl.semantic_search_handoffs,
    "hybrid": cl.hybrid_search_handoffs,
}


def load_cases(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    cases = data.get("cases") if isinstance(data, dict) else data
    if not isinstance(cases, list) or not cases:
        raise ValueError("Dataset must be a non-empty list or an object with a non-empty 'cases' list")
    for i, case in enumerate(cases, 1):
        if not isinstance(case, dict) or not all(
            isinstance(case.get(key), str) and case[key].strip()
            for key in ("query", "task_slug")
        ):
            raise ValueError(f"Case {i} needs non-empty 'query' and 'task_slug' strings")
        ids = case.get("relevant_ids")
        if not isinstance(ids, list) or not ids or any(not isinstance(x, str) or not x.strip() for x in ids):
            raise ValueError(f"Case {i} needs a non-empty 'relevant_ids' list of handoff ID strings")
    return cases


async def evaluate(cases: list[dict], mode: str, k: int) -> dict:
    search = SEARCH[mode]
    rows = []
    for case in cases:
        hits = await search(case["query"], task_slug=case["task_slug"], limit=k)
        ranked = list(dict.fromkeys(str(hit["id"]) for hit in hits if hit.get("id") is not None))
        relevant = set(case["relevant_ids"])
        ranks = [rank for rank, handoff_id in enumerate(ranked, 1) if handoff_id in relevant]
        rows.append({
            "query": case["query"],
            "task_slug": case["task_slug"],
            "relevant_count": len(relevant),
            "returned_ids": ranked,
            "hit": bool(ranks),
            "recall_at_k": len(ranks) / len(relevant),
            "precision_at_k": len(ranks) / k,
            "reciprocal_rank_at_k": 1 / ranks[0] if ranks else 0.0,
        })

    count = len(rows)
    return {
        "search": mode,
        "k": k,
        "query_count": count,
        "hit_rate_at_k": sum(row["hit"] for row in rows) / count,
        "mean_recall_at_k": sum(row["recall_at_k"] for row in rows) / count,
        "mean_precision_at_k": sum(row["precision_at_k"] for row in rows) / count,
        "mrr_at_k": sum(row["reciprocal_rank_at_k"] for row in rows) / count,
        "cases": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path, help="JSON file containing labeled retrieval queries")
    parser.add_argument("--search", choices=SEARCH, default="hybrid")
    parser.add_argument("-k", type=int, default=5, help="Number of results per query (default: 5)")
    parser.add_argument("--min-mrr", type=float, help="Fail if mean reciprocal rank is below this value")
    parser.add_argument("--json", action="store_true", help="Print the complete report as JSON")
    args = parser.parse_args()
    if args.k < 1:
        parser.error("-k must be at least 1")
    try:
        report = asyncio.run(evaluate(load_cases(args.dataset), args.search, args.k))
    except (OSError, json.JSONDecodeError, ValueError, KeyError) as exc:
        parser.error(str(exc))

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"Search: {report['search']} | queries: {report['query_count']} | k: {report['k']}")
        print(f"Hit rate@{args.k}: {report['hit_rate_at_k']:.3f}")
        print(f"Mean recall@{args.k}: {report['mean_recall_at_k']:.3f}")
        print(f"Mean precision@{args.k}: {report['mean_precision_at_k']:.3f}")
        print(f"MRR@{args.k}: {report['mrr_at_k']:.3f}")
        for i, case in enumerate(report["cases"], 1):
            status = "hit" if case["hit"] else "MISS"
            print(f"{i}. [{status}] {case['query']} (MRR={case['reciprocal_rank_at_k']:.3f})")

    return int(args.min_mrr is not None and report["mrr_at_k"] < args.min_mrr)


if __name__ == "__main__":
    raise SystemExit(main())
