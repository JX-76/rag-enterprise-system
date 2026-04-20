# Rewrite and Routing Ablation Study

## Research Question

When should query rewriting be enabled in a knowledge-base QA pipeline, and does routing-aware rewrite improve retrieval quality compared with always-on or no-rewrite baselines?

---

## Compared Strategies

### Baseline A: No Rewrite
- direct retrieval with the original user query
- lowest latency
- may underperform on underspecified or conversational queries

### Baseline B: Always Rewrite
- apply rewrite / expansion for all queries
- stronger normalization and semantic broadening
- may inject noise for exact lookup or already well-formed queries

### Variant: Routing-aware Rewrite
- use lightweight query routing to decide when rewrite should be enabled
- exact lookup queries may bypass rewrite
- complex / ambiguous / summarization queries may enable rewrite

---

## Controlled Variables

Keep fixed:
- same corpus
- same chunking strategy
- same retriever
- same reranker
- same generation model
- same query set

Only the **rewrite / routing policy** changes.

---

## Suggested Metrics

### Retrieval Metrics
- Recall@5
- MRR
- nDCG@5

### Routing Metrics
- route correctness (sampled/manual)
- rewrite trigger rate
- exact-lookup bypass correctness

### Efficiency Metrics
- average latency
- rewrite overhead

---

## Suggested Result Table

| Strategy | Recall@5 | MRR | nDCG@5 | Route Correctness | Rewrite Trigger Rate | Avg Latency | Notes |
|---|---:|---:|---:|---:|---:|---:|---|
| No Rewrite | TBD | TBD | TBD | N/A | 0% | TBD | strong baseline for exact lookup |
| Always Rewrite | TBD | TBD | TBD | N/A | 100% | TBD | may add noise |
| Routing-aware Rewrite | TBD | TBD | TBD | TBD | TBD | TBD | targeted rewrite activation |

---

## Analysis Questions

- Does always-on rewrite help or hurt exact lookup queries?
- Does routing-aware rewrite preserve exact-match quality while improving hard-query recall?
- What latency overhead is introduced by rewrite?
- How often does the router make the expected rewrite decision?

---

## Reporting Guidance

Prefer writing:
- "we compared no-rewrite, always-rewrite, and routing-aware rewrite policies to quantify the trade-off between recall gains and rewrite-induced noise."

Avoid writing only:
- "we added query rewriting to improve retrieval"

---

## References to Mention

Use references as methodological anchors:
- conversational query rewriting for retrieval
- query expansion and multi-query retrieval techniques
- retrieval optimization practices in RAG pipelines
