# 微调数据规划

## Goal

Add a **real, lightweight, project-defensible fine-tuning branch** to the project without bloating it into a fake large-model training platform.

The default target is:
- **Query Rewrite Fine-tuning**

Optional second target:
- **Reranker / Embedding Fine-tuning**

---

## 1. Query Rewrite Fine-tuning

### 1.1 Task definition
Train a small model to transform noisy / short / ambiguous user queries into retrieval-friendly rewritten queries.

### 1.2 Why this is the best first fine-tuning task
- directly connected to retrieval quality
- data is easier to construct than full SFT data
- fits LoRA / QLoRA on a small model
- can be evaluated with Recall@K / MRR / NDCG
- integrates naturally into the existing RAG pipeline

### 1.3 Recommended data format
Store JSONL files under:

```text
data/ft/
  rewrite_train.jsonl
  rewrite_dev.jsonl
  rewrite_test.jsonl
```

Each row:

```json
{"query":"RAG怎么减少幻觉","rewrite":"RAG 通过哪些机制减少大模型幻觉"}
```

Recommended richer format:

```json
{
  "id": "rw_001",
  "query": "RAG怎么减少幻觉",
  "rewrite": "RAG 通过哪些机制减少大模型幻觉",
  "intent": "query_rewrite",
  "source": "manual_curated",
  "difficulty": "easy"
}
```

### 1.4 Data sources
Build from three sources:

1. repo-grounded evaluation set
   - `data/eval/repo_grounded_eval_v1.jsonl`
2. project docs
   - README / ARCHITECTURE / API / ROADMAP / STRUCTURE_GUIDE
3. manually curated user-style queries
   - colloquial / short / underspecified / ambiguous queries

### 1.5 Data construction rules
The rewritten query should:
- preserve original intent
- add missing retrieval cues
- normalize colloquial phrasing
- avoid adding unsupported facts
- avoid rewriting into a different task

### 1.6 Minimum dataset target
For v1:
- train: 150–300 rows
- dev: 30–50 rows
- test: 30–50 rows

This is enough for a small, believable LoRA experiment.

---

## 2. Optional Reranker Fine-tuning

### 2.1 Task definition
Train a ranking model on query / positive-doc / negative-doc pairs.

### 2.2 Data format

```text
data/ft/
  rerank_train.jsonl
  rerank_dev.jsonl
  rerank_test.jsonl
```

Example row:

```json
{
  "query": "什么是 hybrid retrieval",
  "positive": "混合检索结合 dense 和 sparse 检索...",
  "negative": "部署方式包括 Docker Compose 和 Kubernetes..."
}
```

### 2.3 Why it is useful
- directly improves top-k ranking quality
- more retrieval-realistic than generic instruction tuning
- supports strong metric-based evaluation

---

## 3. Training Strategy

### Recommended first model
- Qwen2.5-1.5B / 3B class model for rewrite FT
- LoRA / QLoRA style adaptation

### Why
- low training cost
- realistic for a personal project
- good enough to support a project story
- easier to run than large generator fine-tuning

---

## 4. Integration Plan

Add new paths:

```text
src/retrieval/rewrite/
  baseline_rewriter.py
  ft_rewriter.py
```

And scripts:

```text
scripts/
  prepare_rewrite_ft_data.py
  train_rewrite_lora.py
  eval_rewrite_ft.py
```

Artifacts:

```text
artifacts/ft/
  rewrite-lora/
```

---

## 5. Evaluation Requirements

Every fine-tuning experiment must compare:
- baseline RAG
- RAG + FT rewrite

Report:
- Recall@1 / 3 / 5
- MRR
- NDCG@5
- avg latency
- p95 latency
- training cost / inference overhead
- at least 5 bad cases

---

## 6. Resume-safe story

Good story:

> Built a modular RAG baseline, then added a retrieval-oriented fine-tuning branch on a small query-rewrite model using LoRA, and measured the impact with Recall@K / MRR / latency ablations.

Bad story:

> Did RAG and fine-tuning on a large model.

---

## 7. v1 Completion Standard

Fine-tuning v1 is complete only if:
- dataset exists
- train/dev/test split exists
- training script exists
- baseline vs FT evaluation exists
- metrics are reproducible
- bad cases are recorded
