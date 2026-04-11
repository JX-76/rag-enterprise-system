# Evaluation Plan

## Goal

Produce **resume-safe** and **interview-defensible** evaluation results for this repository.

The target is not to generate pretty numbers.
The target is to generate numbers that can survive follow-up questions.

---

## Evaluation Principles

1. **Use a real labeled dataset**
2. **Keep the corpus inspectable**
3. **Define one stable baseline**
4. **Change one variable at a time**
5. **Report both quality and cost**
6. **Keep bad cases**

---

## Scope of v1 Evaluation

### Corpus type
For v1, use a **repo-grounded corpus**:
- `README.md`
- `ARCHITECTURE.md`
- `API.md`
- `DEPLOYMENT.md`
- `docs/ROADMAP.md`
- `docs/STRUCTURE_GUIDE.md`
- selected example/demo scripts

This is intentionally small, but it is:
- real
- inspectable
- reproducible
- easy to defend

### Eval set size
Recommended v1 size:
- **30–50 labeled queries**

Current seed file prepared:
- `data/eval/repo_grounded_eval_v1.jsonl`

---

## Baseline Definition

The default baseline should be fixed as:

- chunking: **fixed chunk**
- retrieval: **dense only**
- rewrite: **off**
- rerank: **off**

This baseline should not change during v1 experiments.

---

## Core Experiments

### Experiment A — Chunking Ablation
Compare:
- fixed chunk
- parent-child chunking

Report:
- Recall@1 / 3 / 5
- MRR
- NDCG@5
- avg latency
- p95 latency

### Experiment B — Retrieval Ablation
Compare:
- dense only
- hybrid retrieval

Report:
- Recall@1 / 3 / 5
- MRR
- NDCG@5
- avg latency
- p95 latency

### Experiment C — Rewrite Ablation
Compare:
- no rewrite
- query rewrite

Report:
- Recall@1 / 3 / 5
- MRR
- NDCG@5
- avg latency
- p95 latency

### Experiment D — Optional Rerank Ablation
Compare:
- retrieval only
- retrieval + rerank

Report the same metrics and the latency increase.

---

## Resume-Safe Metric Types

### Quality Metrics
- Recall@K
- MRR
- NDCG@K

### Cost / Performance Metrics
- average latency
- p95 latency
- ingest latency (optional)
- index build latency (optional)

### Engineering Cleanup Metrics
- noisy root docs removed
- primary API entry consolidated
- example/demo entrypoints consolidated
- test / evaluation utilities stabilized

---

## What NOT to Use as Resume Metrics

Do not use these directly:
- sample benchmark numbers without labeled data
- mock fallback experiment results
- numbers produced under undocumented dependencies / incomplete pipeline setup
- vague claims like "significantly improved retrieval"

---

## Required Output Files

v1 evaluation should end with:

1. `data/eval/repo_grounded_eval_v1.jsonl`
2. `docs/EVAL_REPORT.md`
3. one runnable evaluation script, e.g.
   - `scripts/eval_retrieval.py`
4. one result artifact file, e.g.
   - `artifacts/eval/retrieval_eval_v1.json`

---

## Bad Case Analysis Template

For each experiment, preserve at least 5 bad cases:

- query id
- query text
- expected source docs
- retrieved docs
- failure type
  - wrong lexical match
  - missed exact term
  - query too broad
  - rewrite introduced noise
  - chunk lost context
- takeaway

These bad cases are extremely useful in interviews.

---

## Acceptance Criteria

v1 evaluation is complete only if:

- at least 30 queries are labeled
- baseline is fixed and documented
- at least 3 ablations are run
- results contain both quality metrics and latency metrics
- at least 5 bad cases are documented
- all reported numbers can be reproduced with a single script and a clear config

---

## Suggested Resume Wording Pattern

Use results like this:

- Built a labeled repo-grounded eval set and ran retrieval ablations across chunking / hybrid retrieval / query rewrite variants.
- Improved **Recall@5** from **X** to **Y** under a fixed baseline, while keeping **P95 latency** within **Z ms**.
- Used ablation analysis and bad-case review to guide retrieval quality improvements instead of relying on anecdotal prompts.

Only fill in X / Y / Z after the real eval is complete.
