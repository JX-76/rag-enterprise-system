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

AUGMENT_PREFIXES = [
    "帮我讲讲",
    "简单说下",
    "想确认一下",
    "我想知道",
]

CASUAL_REPLACEMENTS = [
    ("这个项目", "项目里"),
    ("该项目", "项目里"),
    ("如何", "怎么"),
    ("为什么", "为啥"),
    ("是什么", "是啥"),
    ("包含哪些", "包括哪些"),
    ("当前", "现在"),
    ("当前版本", "现在这个版本"),
    ("当前仓库", "现在仓库"),
    ("当前主打", "现在主打"),
    ("当前评估体系", "现在评估体系"),
    ("当前项目", "现在项目"),
    ("推荐", "建议"),
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


def build_augmented_query(query: str, idx: int) -> str:
    casual = query.strip()
    for old, new in CASUAL_REPLACEMENTS:
        casual = casual.replace(old, new)
    if not casual.endswith("？"):
        casual = casual.rstrip("。") + "？"
    prefix = AUGMENT_PREFIXES[idx % len(AUGMENT_PREFIXES)]
    return f"{prefix}{casual}"


def make_row(sample: dict) -> dict:
    return {
        "id": sample["id"],
        "query": sample["query"],
        "rewrite": build_rewrite(sample),
        "source": "repo_grounded_eval_v1",
        "category": sample.get("category", "general"),
        "difficulty": sample.get("difficulty", "medium"),
    }


def make_augmented_row(sample: dict, idx: int) -> dict:
    base = make_row(sample)
    base["id"] = f"{sample['id']}_aug{idx + 1}"
    base["query"] = build_augmented_query(sample["query"], idx)
    base["source"] = "repo_grounded_eval_v1_augmented"
    return base


def main() -> None:
    if not SRC.exists():
        raise FileNotFoundError(f"Missing source eval file: {SRC}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    samples = []
    with SRC.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            sample = json.loads(line)
            samples.append(sample)

    random.seed(42)
    random.shuffle(samples)

    n = len(samples)
    train_end = int(n * 0.7)
    dev_end = int(n * 0.85)

    train_samples = samples[:train_end]
    dev_samples = samples[train_end:dev_end]
    test_samples = samples[dev_end:]

    train_rows = [make_row(sample) for sample in train_samples]
    train_rows += [make_augmented_row(sample, idx=0) for sample in train_samples]

    dev_rows = [make_row(sample) for sample in dev_samples]
    dev_rows += [make_augmented_row(sample, idx=1) for sample in dev_samples]

    test_rows = [make_row(sample) for sample in test_samples]

    splits = {
        "rewrite_train.jsonl": train_rows,
        "rewrite_dev.jsonl": dev_rows,
        "rewrite_test.jsonl": test_rows,
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
