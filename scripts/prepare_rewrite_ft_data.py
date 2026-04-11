#!/usr/bin/env python3
"""
Build lightweight query-rewrite fine-tuning datasets from existing repo-grounded eval data.

Input:
  data/eval/repo_grounded_eval_v1.jsonl

Output:
  data/ft/rewrite_train.jsonl
  data/ft/rewrite_dev.jsonl
  data/ft/rewrite_test.jsonl

This script generates a first-pass dataset skeleton. It is intentionally simple
and should be followed by manual review / cleanup before actual training.
"""
from __future__ import annotations

import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "eval" / "repo_grounded_eval_v1.jsonl"
OUT_DIR = ROOT / "data" / "ft"


PREFIX_RULES = [
    "请解释",
    "请详细说明",
    "从检索优化角度解释",
    "从系统设计角度解释",
]


def normalize_query(q: str) -> str:
    q = q.strip().replace("这个项目", "该项目")
    return q


def build_rewrite(sample: dict) -> str:
    query = normalize_query(sample["query"])
    category = sample.get("category", "general")
    answer_points = sample.get("answer_points", [])

    prefix = random.choice(PREFIX_RULES)
    suffix = ""

    if category in {"evaluation", "retrieval", "rewrite", "rerank", "chunking"}:
        suffix = "，并指出它与检索效果或评测指标的关系"
    elif category in {"positioning", "structure", "architecture"}:
        suffix = "，并说明它在项目架构或定位中的作用"
    elif category in {"api", "deployment"}:
        suffix = "，并说明它在系统接入或运行流程中的位置"

    if answer_points:
        hint = "、".join(answer_points[:2])
        return f"{prefix}{query}{suffix}，重点覆盖：{hint}"

    return f"{prefix}{query}{suffix}"


def main() -> None:
    if not SRC.exists():
        raise FileNotFoundError(f"Missing source eval file: {SRC}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    rows = []
    with SRC.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            sample = json.loads(line)
            rows.append({
                "id": sample["id"],
                "query": sample["query"],
                "rewrite": build_rewrite(sample),
                "source": "repo_grounded_eval_v1",
                "category": sample.get("category", "general"),
                "difficulty": sample.get("difficulty", "medium"),
            })

    random.seed(42)
    random.shuffle(rows)

    n = len(rows)
    train_end = int(n * 0.7)
    dev_end = int(n * 0.85)

    splits = {
        "rewrite_train.jsonl": rows[:train_end],
        "rewrite_dev.jsonl": rows[train_end:dev_end],
        "rewrite_test.jsonl": rows[dev_end:],
    }

    for name, data in splits.items():
        path = OUT_DIR / name
        with path.open("w", encoding="utf-8") as f:
            for row in data:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"wrote {len(data):>3} rows -> {path.relative_to(ROOT)}")

    print("\nDone. Please manually review rewrites before training.")


if __name__ == "__main__":
    main()
