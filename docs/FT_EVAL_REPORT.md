# 微调评测报告模板

## Experiment Goal

Evaluate whether adding a **fine-tuned query rewrite module** improves the retrieval side of the modular RAG pipeline.

---

## Variants

### Baseline
- chunking: fixed / current baseline
- retrieval: baseline retrieval
- rewrite: baseline rewrite or no rewrite
- rerank: baseline setting

### FT Variant
- same pipeline as baseline
- only change: **fine-tuned rewrite model**

---

## Dataset

- eval set: `data/eval/repo_grounded_eval_v1.jsonl`
- FT data:
  - `data/ft/rewrite_train.jsonl`
  - `data/ft/rewrite_dev.jsonl`
  - `data/ft/rewrite_test.jsonl`

---

## Metrics

### Quality
- Recall@1
- Recall@3
- Recall@5
- MRR
- NDCG@5

### Performance
- average latency
- p95 latency
- inference overhead vs baseline

### Training-side notes
- base model
- LoRA config
- train epochs
- train set size
- dev set size

---

## Results Table

| Variant | Recall@1 | Recall@3 | Recall@5 | MRR | NDCG@5 | Avg Latency | P95 Latency |
|--------|----------|----------|----------|-----|---------|-------------|-------------|
| Baseline | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| RAG + FT Rewrite | TBD | TBD | TBD | TBD | TBD | TBD | TBD |

---

## Main Findings

1. Did FT rewrite improve retrieval quality?
2. Which metrics improved most?
3. What was the latency cost?
4. Was the gain large enough to justify the added complexity?

---

## Bad Cases

At least 5 cases:

| Query | Baseline Issue | FT Result | Verdict |
|------|----------------|-----------|---------|
| TBD | TBD | TBD | TBD |

---

## Conclusion

Use this section for a public-safe summary, for example:

> Under a fixed modular RAG baseline, adding a fine-tuned query rewrite module improved retrieval metrics on the repo-grounded eval set while introducing limited inference overhead.

Do not fill this with claims until real numbers are produced.
