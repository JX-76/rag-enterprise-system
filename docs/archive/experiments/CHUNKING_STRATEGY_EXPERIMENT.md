# Chunking Strategy Experiment Design

## Research Question

How do different chunking strategies affect retrieval quality, support coverage, and latency in the enterprise knowledge-base QA setting?

---

## Compared Strategies

### Baseline A: Fixed Small Chunks
- smaller chunk size
- stronger local matching
- risk: context fragmentation

### Baseline B: Fixed Large Chunks
- larger chunk size
- stronger context completeness
- risk: retrieval noise / lower precision

### Variant: Parent-Child Chunking
- child chunks for retrieval
- parent chunks for answer grounding / generation
- target: balance retrieval precision and context completeness

---

## Controlled Variables

To keep the comparison fair, the following variables should remain fixed:

- same document corpus
- same query set
- same embedding model
- same retrieval backend
- same reranker configuration
- same generation model
- same evaluation script and metric implementation

Only the **chunking strategy** changes.

---

## Metrics

### Retrieval Metrics
- Recall@1
- Recall@5
- MRR
- nDCG@5

### Support / Answer-Level Metrics
- support rate
- citation coverage
- unsupported answer rate (manual / sampled)

### System Metrics
- average latency
- p95 latency
- total chunk count
- index size proxy

---

## Expected Analysis Dimensions

### 1. Retrieval Quality
- Does small chunking improve exact hit rate?
- Does large chunking reduce fragmentation but introduce more noise?
- Does parent-child strike a better balance?

### 2. Context Quality
- Does parent-child improve support completeness for generated answers?
- Are citations more coherent under parent-child than under fixed small chunks?

### 3. Efficiency Trade-off
- Does the number of chunks significantly affect retrieval latency?
- What is the cost of improved recall / support?

---

## Suggested Result Table

| Strategy | Recall@1 | Recall@5 | MRR | nDCG@5 | Support Rate | Avg Latency | Notes |
|---|---:|---:|---:|---:|---:|---:|---|
| Fixed Small | TBD | TBD | TBD | TBD | TBD | TBD | better local precision, more fragmentation |
| Fixed Large | TBD | TBD | TBD | TBD | TBD | TBD | more context, more noise |
| Parent-Child | TBD | TBD | TBD | TBD | TBD | TBD | balanced retrieval and grounding |

---

## Reporting Guidance

When writing project documentation, avoid saying only:
- "we used parent-child chunking"

Prefer saying:
- "we compared fixed-size and parent-child chunking under the same corpus, query set, and retrieval stack, and evaluated them with Recall@K, MRR, support rate, and latency to understand the trade-off between retrieval precision and context completeness."

---

## References to Mention

Use references as design motivation rather than fake citation padding:
- hierarchical / parent-child retrieval patterns in production RAG
- long-context retrieval and chunking trade-offs in RAG engineering writeups
- retrieval-grounded QA evaluation practices
