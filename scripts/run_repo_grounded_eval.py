#!/usr/bin/env python3
"""Run a fixed repo-grounded evaluation protocol and persist a versioned artifact."""
from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.core.rag_engine import RAGEngine
from src.evaluation.metrics import BenchmarkRunner

DEFAULT_DATASET: List[Dict[str, Any]] = [
    {
        "query": "系统支持哪些检索优化能力？",
        "relevant_docs": ["README.md", "ARCHITECTURE.md"],
    },
    {
        "query": "当检索证据不足时，系统会怎么处理？",
        "relevant_docs": [
            "README.md",
            "ARCHITECTURE.md",
            "docs/AGENT_HARNESS_GAP_ANALYSIS.md",
            "docs/ROADMAP.md",
        ],
    },
    {
        "query": "为什么要输出 structured execution trace？",
        "relevant_docs": [
            "README.md",
            "ARCHITECTURE.md",
            "docs/AGENT_HARNESS_GAP_ANALYSIS.md",
        ],
    },
]


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True
        ).strip()
    except Exception:
        return "unknown"


def _mean(values: List[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _load_jsonl_dataset(path: Path) -> List[Dict[str, Any]]:
    dataset: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        dataset.append(json.loads(line))
    return dataset


async def _run_once(dataset: List[Dict[str, Any]]) -> Dict[str, Any]:
    engine = RAGEngine()
    runner = BenchmarkRunner(engine)
    return await runner.run_benchmark(dataset)


async def _run_many(dataset: List[Dict[str, Any]], runs: int, dataset_name: str) -> Dict[str, Any]:
    reports: List[Dict[str, Any]] = []
    for _ in range(runs):
        reports.append(await _run_once(dataset))

    latest = reports[-1]

    recall_vals = [r["retrieval"]["recall@20"] for r in reports]
    p3_vals = [r["retrieval"]["precision@3"] for r in reports]
    mrr_vals = [r["retrieval"]["mrr"] for r in reports]
    map_vals = [r["retrieval"]["map"] for r in reports]
    faith_vals = [r["generation"]["avg_faithfulness"] for r in reports]
    rel_vals = [r["generation"]["avg_relevance"] for r in reports]
    hall_vals = [r["generation"]["avg_hallucination"] for r in reports]
    latency_vals = [r["performance"]["avg_latency_ms"] for r in reports]
    support_vals = [r["performance"]["avg_support_confidence"] for r in reports]
    badcase_vals = [len(r.get("details", {}).get("badcases", [])) for r in reports]

    latest.setdefault("meta", {})["note"] = "repo-grounded-engineering-eval"
    latest["meta"]["git_commit"] = _git_commit()
    latest["meta"]["protocol"] = {
        "script": "scripts/run_repo_grounded_eval.py",
        "runs": runs,
        "dataset_name": dataset_name,
    }
    latest["meta"]["dataset"] = dataset
    latest["meta"]["stability_summary"] = {
        "runs": runs,
        "min_recall@20": min(recall_vals),
        "max_recall@20": max(recall_vals),
        "avg_recall@20": _mean(recall_vals),
        "min_precision@3": min(p3_vals),
        "max_precision@3": max(p3_vals),
        "avg_precision@3": _mean(p3_vals),
        "min_mrr": min(mrr_vals),
        "max_mrr": max(mrr_vals),
        "avg_mrr": _mean(mrr_vals),
        "min_map": min(map_vals),
        "max_map": max(map_vals),
        "avg_map": _mean(map_vals),
        "min_faithfulness": min(faith_vals),
        "max_faithfulness": max(faith_vals),
        "avg_faithfulness": _mean(faith_vals),
        "min_relevance": min(rel_vals),
        "max_relevance": max(rel_vals),
        "avg_relevance": _mean(rel_vals),
        "min_hallucination": min(hall_vals),
        "max_hallucination": max(hall_vals),
        "avg_hallucination": _mean(hall_vals),
        "avg_latency_ms": _mean(latency_vals),
        "avg_support_confidence": _mean(support_vals),
        "max_badcases": max(badcase_vals),
    }
    return latest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=int, default=10, help="number of repeated runs")
    parser.add_argument(
        "--dataset-file",
        default="",
        help="optional JSONL dataset path relative to repo root",
    )
    parser.add_argument(
        "--output-dir",
        default="artifacts/eval/optimization_runs",
        help="artifact output directory",
    )
    args = parser.parse_args()

    if args.dataset_file:
        dataset_path = (ROOT / args.dataset_file).resolve()
        dataset = _load_jsonl_dataset(dataset_path)
        dataset_name = str(dataset_path.relative_to(ROOT))
    else:
        dataset = DEFAULT_DATASET
        dataset_name = "repo_grounded_eval_v1_inline"

    report = asyncio.run(_run_many(dataset, args.runs, dataset_name))

    out_dir = ROOT / args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = out_dir / f"repo_grounded_eval_{stamp}.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(out_path.relative_to(ROOT))
    print(json.dumps({
        "dataset_name": dataset_name,
        "dataset_size": len(dataset),
        **report["meta"]["stability_summary"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
