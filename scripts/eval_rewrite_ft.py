#!/usr/bin/env python3
"""
Evaluate baseline rewrite vs fine-tuned rewrite on the repo-grounded dataset.

This is a lightweight evaluation scaffold focused on:
- data integrity
- rewrite validity tracking
- latency measurement
- report-ready output format

It does NOT fabricate retrieval gains. Those fields remain null until a real
retrieval backend is wired in and executed.
"""
from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parent.parent
EVAL_FILE = ROOT / "data" / "eval" / "repo_grounded_eval_v1.jsonl"
FT_TEST_FILE = ROOT / "data" / "ft" / "rewrite_test.jsonl"


def load_jsonl(path: Path) -> List[Dict]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def baseline_rewrite(query: str) -> str:
    return query.strip()


def ft_rewrite(sample: Dict) -> str:
    return sample.get("rewrite", sample.get("query", "")).strip()


def simple_validity(query: str, rewrite: str) -> bool:
    return bool(query.strip()) and bool(rewrite.strip()) and len(rewrite) >= len(query) * 0.6


def summarize_latency(values: List[float]) -> Dict[str, float]:
    values = sorted(values)
    if not values:
        return {"avg_ms": 0.0, "p95_ms": 0.0, "min_ms": 0.0, "max_ms": 0.0}
    idx = max(0, min(len(values) - 1, int(len(values) * 0.95) - 1))
    return {
        "avg_ms": round(statistics.mean(values), 3),
        "p95_ms": round(values[idx], 3),
        "min_ms": round(values[0], 3),
        "max_ms": round(values[-1], 3),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate rewrite FT scaffold")
    parser.add_argument("--eval-file", default=str(EVAL_FILE))
    parser.add_argument("--ft-file", default=str(FT_TEST_FILE))
    parser.add_argument("--output", default="artifacts/eval/rewrite_ft_eval.json")
    args = parser.parse_args()

    eval_rows = load_jsonl(Path(args.eval_file))
    ft_rows = load_jsonl(Path(args.ft_file))
    ft_map = {row["id"]: row for row in ft_rows if "id" in row}

    baseline_lat = []
    ft_lat = []
    baseline_valid = 0
    ft_valid = 0
    compared = 0
    samples = []

    for row in eval_rows:
        query = row["query"]
        rid = row["id"]

        t0 = time.perf_counter()
        base_rw = baseline_rewrite(query)
        baseline_lat.append((time.perf_counter() - t0) * 1000)
        baseline_valid += int(simple_validity(query, base_rw))

        if rid not in ft_map:
            continue

        t1 = time.perf_counter()
        ft_rw = ft_rewrite(ft_map[rid])
        ft_lat.append((time.perf_counter() - t1) * 1000)
        ft_valid += int(simple_validity(query, ft_rw))
        compared += 1

        if len(samples) < 5:
            samples.append({
                "id": rid,
                "query": query,
                "baseline_rewrite": base_rw,
                "ft_rewrite": ft_rw,
            })

    result = {
        "dataset": {
            "eval_rows": len(eval_rows),
            "ft_rows": len(ft_rows),
            "compared_rows": compared,
        },
        "baseline_rewrite": {
            "valid_rate": round(baseline_valid / len(eval_rows), 4) if eval_rows else 0.0,
            **summarize_latency(baseline_lat),
        },
        "ft_rewrite": {
            "valid_rate": round(ft_valid / compared, 4) if compared else 0.0,
            **summarize_latency(ft_lat),
        },
        "retrieval_metrics": {
            "recall_at_1": None,
            "recall_at_3": None,
            "recall_at_5": None,
            "mrr": None,
            "ndcg_at_5": None,
            "note": "Not filled until real retrieval evaluation is executed against a wired retrieval backend."
        },
        "samples": samples,
    }

    out = ROOT / args.output
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print("=" * 70)
    print("Rewrite FT Evaluation Scaffold")
    print("=" * 70)
    print(f"compared rows       : {compared}")
    print(f"baseline valid rate : {result['baseline_rewrite']['valid_rate']:.2%}")
    print(f"ft valid rate       : {result['ft_rewrite']['valid_rate']:.2%}")
    print(f"baseline avg ms     : {result['baseline_rewrite']['avg_ms']}")
    print(f"ft avg ms           : {result['ft_rewrite']['avg_ms']}")
    print(f"output              : {out.relative_to(ROOT)}")
    print("\nNote: retrieval quality metrics are intentionally left null until a real backend run is completed.")


if __name__ == "__main__":
    main()
