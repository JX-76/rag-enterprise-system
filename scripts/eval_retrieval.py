#!/usr/bin/env python3
"""
Repo-grounded retrieval evaluation.

Purpose:
- produce reproducible retrieval metrics on a small inspectable corpus
- compare baseline query vs rewrite-enhanced query
- avoid external dependencies so the script can run in minimal environments

Outputs:
- artifacts/eval/retrieval_eval_v1.json
"""
from __future__ import annotations

import argparse
import json
import math
import re
import statistics
import time
from collections import Counter
from pathlib import Path
from typing import Dict, List, Set

ROOT = Path(__file__).resolve().parent.parent
EVAL_FILE = ROOT / "data" / "eval" / "repo_grounded_eval_v1.jsonl"
FT_FILES = [
    ROOT / "data" / "ft" / "rewrite_train.jsonl",
    ROOT / "data" / "ft" / "rewrite_dev.jsonl",
    ROOT / "data" / "ft" / "rewrite_test.jsonl",
]


def load_jsonl(path: Path) -> List[Dict]:
    rows: List[Dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def normalize(text: str) -> str:
    return text.lower().strip()


def tokenize(text: str) -> List[str]:
    text = normalize(text)
    tokens: List[str] = []
    tokens += re.findall(r"[a-zA-Z_][a-zA-Z0-9_:\./-]*", text)
    tokens += re.findall(r"\d+", text)
    cjk_chars = [ch for ch in text if "\u4e00" <= ch <= "\u9fff"]
    tokens += cjk_chars
    tokens += ["".join(cjk_chars[i : i + 2]) for i in range(len(cjk_chars) - 1)]
    return tokens


class BM25LiteRetriever:
    def __init__(self, corpus: Dict[str, str]):
        self.corpus = corpus
        self.doc_tokens = {
            doc_id: tokenize(doc_id + "\n" + text[:20000]) for doc_id, text in corpus.items()
        }
        self.num_docs = len(self.doc_tokens)
        self.avgdl = sum(len(v) for v in self.doc_tokens.values()) / max(1, self.num_docs)
        self.df = Counter()
        for toks in self.doc_tokens.values():
            for tok in set(toks):
                self.df[tok] += 1
        self.k1 = 1.5
        self.b = 0.75

    def _score(self, query: str, doc_id: str) -> float:
        q_tokens = tokenize(query)
        tf = Counter(self.doc_tokens[doc_id])
        dl = len(self.doc_tokens[doc_id])
        score = 0.0
        for tok in q_tokens:
            if tok not in tf:
                continue
            idf = math.log(1 + (self.num_docs - self.df[tok] + 0.5) / (self.df[tok] + 0.5))
            freq = tf[tok]
            score += idf * (freq * (self.k1 + 1)) / (freq + self.k1 * (1 - self.b + self.b * dl / self.avgdl))
        return score

    def retrieve(self, query: str, top_k: int = 10) -> List[str]:
        return sorted(self.corpus, key=lambda doc_id: (self._score(query, doc_id), doc_id), reverse=True)[:top_k]


def precision_at_k(ranked: List[str], relevant: Set[str], k: int) -> float:
    if k <= 0:
        return 0.0
    return len(set(ranked[:k]) & relevant) / k


def recall_at_k(ranked: List[str], relevant: Set[str], k: int) -> float:
    if not relevant:
        return 0.0
    return len(set(ranked[:k]) & relevant) / len(relevant)


def reciprocal_rank(ranked: List[str], relevant: Set[str]) -> float:
    for idx, doc_id in enumerate(ranked, 1):
        if doc_id in relevant:
            return 1.0 / idx
    return 0.0


def average_precision(ranked: List[str], relevant: Set[str]) -> float:
    if not relevant:
        return 0.0
    hit_count = 0
    total = 0.0
    for idx, doc_id in enumerate(ranked, 1):
        if doc_id in relevant:
            hit_count += 1
            total += hit_count / idx
    return total / len(relevant)


def ndcg_at_k(ranked: List[str], relevant: Set[str], k: int) -> float:
    def dcg(labels: List[int]) -> float:
        return sum((2**label - 1) / math.log2(i + 2) for i, label in enumerate(labels))

    gains = [1 if doc_id in relevant else 0 for doc_id in ranked[:k]]
    ideal = [1] * min(len(relevant), k)
    denom = dcg(ideal)
    return dcg(gains) / denom if denom > 0 else 0.0


def p95(values: List[float]) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(values)
    idx = max(0, min(len(sorted_values) - 1, math.ceil(len(sorted_values) * 0.95) - 1))
    return sorted_values[idx]


def summarize(results: List[Dict]) -> Dict:
    ks = [1, 3, 5]
    summary = {
        "recall": {},
        "precision": {},
        "mrr": round(statistics.mean(r["mrr"] for r in results), 4),
        "map": round(statistics.mean(r["map"] for r in results), 4),
        "ndcg@5": round(statistics.mean(r["ndcg@5"] for r in results), 4),
        "latency_ms": {
            "avg": round(statistics.mean(r["latency_ms"] for r in results), 3),
            "p95": round(p95([r["latency_ms"] for r in results]), 3),
        },
    }
    for k in ks:
        summary["recall"][str(k)] = round(statistics.mean(r[f"recall@{k}"] for r in results), 4)
        summary["precision"][str(k)] = round(statistics.mean(r[f"precision@{k}"] for r in results), 4)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate repo-grounded retrieval")
    parser.add_argument("--eval-file", default=str(EVAL_FILE))
    parser.add_argument("--output", default="artifacts/eval/retrieval_eval_v1.json")
    parser.add_argument("--top-k", type=int, default=10)
    args = parser.parse_args()

    eval_rows = load_jsonl(Path(args.eval_file))

    ft_rewrites: Dict[str, str] = {}
    for path in FT_FILES:
        if not path.exists():
            continue
        for row in load_jsonl(path):
            base_id = row["id"].split("_aug")[0]
            ft_rewrites.setdefault(base_id, row.get("rewrite", row.get("query", "")).strip())

    doc_paths = sorted({doc for row in eval_rows for doc in row["relevant_docs"]})
    corpus: Dict[str, str] = {}
    for doc_path in doc_paths:
        path = ROOT / doc_path
        try:
            corpus[doc_path] = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            corpus[doc_path] = ""

    retriever = BM25LiteRetriever(corpus)

    by_mode = {"baseline": [], "ft_rewrite": []}
    deltas = []
    bad_cases = []

    for row in eval_rows:
        relevant = set(row["relevant_docs"])
        variants = {
            "baseline": row["query"],
            "ft_rewrite": ft_rewrites.get(row["id"], row["query"]),
        }

        per_query = {}
        for mode, query in variants.items():
            start = time.perf_counter()
            ranked = retriever.retrieve(query, top_k=args.top_k)
            latency_ms = (time.perf_counter() - start) * 1000
            metrics = {
                f"recall@{k}": recall_at_k(ranked, relevant, k) for k in (1, 3, 5)
            }
            metrics.update({
                f"precision@{k}": precision_at_k(ranked, relevant, k) for k in (1, 3, 5)
            })
            metrics.update({
                "mrr": reciprocal_rank(ranked, relevant),
                "map": average_precision(ranked, relevant),
                "ndcg@5": ndcg_at_k(ranked, relevant, 5),
                "latency_ms": latency_ms,
            })
            by_mode[mode].append(metrics)
            per_query[mode] = {"ranked": ranked, **metrics}

        delta_r5 = per_query["ft_rewrite"]["recall@5"] - per_query["baseline"]["recall@5"]
        delta_mrr = per_query["ft_rewrite"]["mrr"] - per_query["baseline"]["mrr"]
        deltas.append({
            "id": row["id"],
            "query": row["query"],
            "delta_recall@5": delta_r5,
            "delta_mrr": delta_mrr,
        })

        if per_query["ft_rewrite"]["recall@5"] < 1.0 or per_query["baseline"]["recall@5"] < 1.0:
            bad_cases.append({
                "id": row["id"],
                "query": row["query"],
                "expected_docs": row["relevant_docs"],
                "baseline_top5": per_query["baseline"]["ranked"][:5],
                "ft_top5": per_query["ft_rewrite"]["ranked"][:5],
                "baseline_recall@5": per_query["baseline"]["recall@5"],
                "ft_recall@5": per_query["ft_rewrite"]["recall@5"],
            })

    baseline = summarize(by_mode["baseline"])
    ft = summarize(by_mode["ft_rewrite"])

    output = {
        "meta": {
            "eval_rows": len(eval_rows),
            "corpus_docs": len(corpus),
            "retriever": "bm25-lite lexical retrieval",
            "baseline": "original query",
            "variant": "ft rewrite query",
            "note": "Repo-grounded first-pass evaluation on an inspectable local corpus.",
        },
        "baseline": baseline,
        "ft_rewrite": ft,
        "deltas": {
            "recall@1": round(ft["recall"]["1"] - baseline["recall"]["1"], 4),
            "recall@3": round(ft["recall"]["3"] - baseline["recall"]["3"], 4),
            "recall@5": round(ft["recall"]["5"] - baseline["recall"]["5"], 4),
            "precision@1": round(ft["precision"]["1"] - baseline["precision"]["1"], 4),
            "precision@3": round(ft["precision"]["3"] - baseline["precision"]["3"], 4),
            "precision@5": round(ft["precision"]["5"] - baseline["precision"]["5"], 4),
            "mrr": round(ft["mrr"] - baseline["mrr"], 4),
            "map": round(ft["map"] - baseline["map"], 4),
            "ndcg@5": round(ft["ndcg@5"] - baseline["ndcg@5"], 4),
            "avg_latency_ms": round(ft["latency_ms"]["avg"] - baseline["latency_ms"]["avg"], 3),
            "p95_latency_ms": round(ft["latency_ms"]["p95"] - baseline["latency_ms"]["p95"], 3),
        },
        "top_improvements": sorted(deltas, key=lambda x: (x["delta_recall@5"], x["delta_mrr"]), reverse=True)[:5],
        "bad_cases": bad_cases[:5],
    }

    out_path = ROOT / args.output
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")

    print("=" * 72)
    print("Repo-grounded Retrieval Evaluation")
    print("=" * 72)
    print(f"eval rows             : {output['meta']['eval_rows']}")
    print(f"corpus docs           : {output['meta']['corpus_docs']}")
    print(f"baseline Recall@5     : {baseline['recall']['5']:.4f}")
    print(f"ft rewrite Recall@5   : {ft['recall']['5']:.4f}")
    print(f"baseline MRR          : {baseline['mrr']:.4f}")
    print(f"ft rewrite MRR        : {ft['mrr']:.4f}")
    print(f"baseline MAP          : {baseline['map']:.4f}")
    print(f"ft rewrite MAP        : {ft['map']:.4f}")
    print(f"baseline avg latency  : {baseline['latency_ms']['avg']:.3f} ms")
    print(f"ft rewrite avg latency: {ft['latency_ms']['avg']:.3f} ms")
    print(f"output                : {out_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
