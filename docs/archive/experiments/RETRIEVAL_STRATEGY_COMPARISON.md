# Retrieval Strategy Comparison

## Research Question

In an enterprise knowledge-base QA setting, how do sparse retrieval, dense retrieval, and hybrid retrieval compare in retrieval quality and robustness across different query types?

---

## Compared Strategies

### Baseline A: BM25 / Sparse Retrieval Only
Strengths:
- exact keyword matching
- strong on identifiers, abbreviations, and precise lexical overlap

Weaknesses:
- weaker semantic generalization
- may miss paraphrased or abstract queries

### Baseline B: Dense Retrieval Only
Strengths:
- semantic similarity
- better handling of paraphrases and fuzzy wording

Weaknesses:
- weaker on exact tokens, codes, version strings, and domain-specific identifiers

### Variant: Hybrid Retrieval
- combine sparse and dense retrieval
- use fusion for broader coverage
- target: improve robustness across both lexical and semantic query types

---

## Controlled Variables

Keep fixed:
- same corpus
- same query set
- same chunking strategy
- same reranker config
- same generation model
- same evaluation metrics

Only the **retrieval strategy** changes.

---

## Suggested Query Subsets

To make the comparison more informative, split evaluation queries into:

- exact lookup queries
- paraphrased / semantic queries
- long-tail queries
- ambiguous / underspecified queries

This helps explain *why* one method performs better, not just *whether* it performs better.

---

## Metrics

### Retrieval Metrics
- Recall@1
- Recall@5
- MRR
- nDCG@5

### Robustness Metrics
- hit rate on exact lookup subset
- hit rate on semantic subset
- hit rate on long-tail subset

### Efficiency Metrics
- average latency
- p95 latency

---

## Suggested Result Table

| Strategy | Recall@1 | Recall@5 | MRR | nDCG@5 | Exact Lookup Hit Rate | Semantic Hit Rate | Avg Latency |
|---|---:|---:|---:|---:|---:|---:|---:|
| Sparse Only | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| Dense Only | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| Hybrid | TBD | TBD | TBD | TBD | TBD | TBD | TBD |

---

## Analysis Questions

- Does sparse retrieval dominate on exact-match questions?
- Does dense retrieval outperform sparse retrieval on paraphrased questions?
- Does hybrid retrieval improve robustness across mixed query types?
- What latency overhead is introduced by hybrid retrieval?

---

## Reporting Guidance

Prefer writing:
- "we compared sparse-only, dense-only, and hybrid retrieval under the same corpus, chunking, and reranker settings to quantify the trade-off between lexical precision, semantic recall, and latency."

Avoid writing only:
- "we used hybrid retrieval because it works better"

---

## References to Mention

Use references as methodological support:
- sparse vs dense retrieval comparisons in open-domain QA and RAG
- hybrid retrieval practices in enterprise search / production RAG
- fusion-based retrieval engineering writeups
