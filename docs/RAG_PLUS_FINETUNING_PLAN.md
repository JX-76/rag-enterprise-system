# RAG + Fine-tuning Plan

## Why shift in this direction

Current market expectations increasingly favor projects that are not just "RAG systems", but **RAG systems with a clear fine-tuning story**.

However, the safe version of that story is **not**:
- claiming full large-model fine-tuning without credible data
- adding a fake LoRA paragraph in the README
- presenting unverified SFT results as if they were production-ready

The safe version is:

> Keep the repository centered on a strong modular RAG baseline, then add one or two **targeted fine-tuning components** that produce measurable improvements.
>
> In practice, any **large-model-facing path** that remains in the public project story should be paired with at least one **lightweight fine-tuning branch**; otherwise the fine-tuning story is incomplete.

---

## Recommended Fine-tuning Targets

### Priority 1 — Fine-tuned Query Rewrite Model
This is the best first choice.

Why:
- tightly coupled to retrieval quality
- easier to build training pairs for
- easier to measure with Recall@K / MRR / NDCG
- low risk of fake-looking "big model fine-tuning" claims

Possible setup:
- small Qwen / Qwen2.5 / similar model
- LoRA / QLoRA style adaptation
- training data = query → rewritten query / multi-query variants / normalized intent form

Project-grade value:
- "Built a retrieval-oriented fine-tuning branch by adapting a small rewrite model and measuring gains on Recall@5 / MRR under a fixed RAG baseline."

### Priority 2 — Fine-tuned Reranker or Embedding Adaptation
This is also strong, but slightly harder.

Why:
- highly relevant to retrieval quality
- more realistic than pretending a giant generator was deeply fine-tuned
- can be evaluated cleanly with ranking metrics

Possible setup:
- positive / negative query-doc pairs
- contrastive or ranking loss
- compare against untuned dense / reranker baseline

Project-grade value:
- "Fine-tuned retrieval-side ranking components to improve top-k relevance and reduce missed relevant chunks."

### Priority 3 — Answer-style / domain-style SFT
This is optional, not first priority.

Why lower priority:
- easier to make look fake if data quality is weak
- harder to prove actual improvement beyond style
- more vulnerable to technical follow-up

Use only if:
- the instruction data is clean
- the effect is measurable
- you can explain exactly what changed

---

## What not to do

Do **not** do the following just to match trend keywords:

- fake a full LLM fine-tuning pipeline
- write "RAG + Fine-tuning" without real training data or metrics
- fine-tune a huge generator first before the retrieval side is even properly evaluated
- report only style/demo improvements with no retrieval or quality metrics

---

## Recommended Roadmap

### Phase 1 — Keep the baseline honest
- stable modular RAG baseline
- real labeled eval set
- baseline retrieval metrics

### Phase 2 — Add one fine-tuned retrieval-side component
Choose one:
- query rewrite fine-tuning
- reranker / embedding fine-tuning

### Phase 3 — Run controlled comparison
Compare:
- baseline RAG
- RAG + FT rewrite
- RAG + FT retrieval-side ranking

### Phase 4 — Report trade-offs
For each variant, report:
- Recall@1 / 3 / 5
- MRR
- NDCG@5
- avg latency
- p95 latency
- training cost / inference overhead
- bad cases

---

## Best public narrative

The strongest realistic story is:

> I first built a modular RAG baseline and made its retrieval path measurable. Then I added a targeted fine-tuning branch on a smaller retrieval-side component instead of pretending to fully fine-tune a large generator. That gave me a more defensible RAG + fine-tuning story with real ablation results and clear trade-offs.

That is much more credible than a vague "I did RAG and fine-tuning" claim.
