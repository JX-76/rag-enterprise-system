# Evaluation Metrics

This project should not rely on qualitative claims alone. Evaluation should be organized around **baseline comparisons, controlled variables, quantitative metrics, and badcase analysis**.

---

## 1. Retrieval Metrics

### Recall@K
Definition:
- whether at least one relevant chunk/document appears in the top-K retrieved results

Why it matters:
- most direct measure of retrieval coverage

Recommended:
- Recall@1
- Recall@5

### MRR (Mean Reciprocal Rank)
Definition:
- reciprocal rank of the first relevant result, averaged over all queries

Why it matters:
- measures how early the first useful hit appears

### nDCG@K
Definition:
- ranking quality with graded relevance

Why it matters:
- useful when multiple relevant documents/chunks exist with different importance

---

## 2. Support / Answer-Level Metrics

### Support Rate
Definition:
- percentage of answers that have at least one clear supporting citation or evidence chunk

Why it matters:
- important for grounded knowledge-base QA

### Unsupported Answer Rate
Definition:
- percentage of answers judged to lack sufficient evidence

Why it matters:
- helps quantify hallucination / over-answering risk

### Citation Coverage
Definition:
- degree to which the generated answer is backed by cited retrieved content

Why it matters:
- complements support rate by checking answer grounding quality

---

## 3. Routing / Execution Metrics

### Route Correctness
Definition:
- manual/sampled evaluation of whether the router chose an appropriate path

Examples:
- exact lookup should bypass rewrite in some cases
- complex reasoning queries may benefit from rewrite + richer retrieval

### Rewrite Trigger Rate
Definition:
- proportion of queries for which rewrite is activated

Why it matters:
- helps explain latency and route behavior

### Fallback Rate
Definition:
- percentage of queries that return support-aware fallback

Why it matters:
- shows how often the system abstains instead of over-answering

### Fallback Correctness
Definition:
- whether fallback occurred in cases where evidence was genuinely insufficient

Why it matters:
- distinguishes useful abstention from overly conservative behavior

---

## 4. Efficiency Metrics

### Average Latency
- mean end-to-end query latency

### P95 Latency
- tail latency under more difficult or slower cases

### Rewrite Overhead
- additional latency introduced by query rewrite

### Rerank Overhead
- additional latency introduced by reranking

---

## 5. Recommended Minimum Reporting Set

For the first round of project documentation, report at least:

- Recall@1
- Recall@5
- MRR
- Average Latency
- P95 Latency
- Support Rate
- Fallback Rate

---

## 6. Reporting Principle

Avoid statements like:
- "the strategy works better"
- "retrieval quality improved significantly"

Prefer statements like:
- "under the same corpus, query set, retriever, and reranker, parent-child chunking improved Recall@5 from TBD to TBD while increasing average latency from TBD to TBD."

This makes the project read more like a research-engineering system and less like a demo.
