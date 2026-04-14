# Agent / Harness Gap Analysis

## Goal

Assess what this repository already has for **Agent / Harness-oriented roles**, what is still missing, and which upgrades are worth implementing without drifting into buzzword-heavy overclaiming.

---

## Short Verdict

This repository is currently strongest as a **production-oriented modular RAG system**.

It is **not yet** a strong Agent / Harness project by default, but it already contains several reusable building blocks that can be reframed and extended toward that direction:

- request-level tracing
- middleware hooks
- modular orchestration structure
- retrieval / rerank / generation boundaries
- experimental agent / workflow / memory folders retained for future expansion

The safest strategy is **not** to pretend this is already a full agent harness.
The safe strategy is to:

1. keep the current retrieval-oriented core honest
2. add a thin execution boundary (routing / structured trace / fallback / support signals)
3. document the harness-oriented extension path clearly

---

## What Agent / Harness interviews usually care about

Compared with general RAG projects, Agent / Harness roles more often probe:

- task routing
- plan / execute / observe loop
- tool reliability and retry strategy
- state transitions
- traceability and auditability
- structured outputs
- interruption / resume hooks
- sandbox / isolation boundaries
- low-confidence / failure fallback
- evaluation beyond answer quality (task success, tool-call success, loop stability)

A repository that only says "we used BM25 + reranker + LLM" will usually look too shallow for those roles.

---

## What this repo already has that can support that story

### 1. Modular pipeline boundaries
Already visible:
- `src/core/rag_engine.py`
- `src/retrieval/`
- `src/rerank/`
- `src/generation/`
- `src/api/`

Why it matters:
- harness work needs stage boundaries, not one giant script
- this repo already has enough structure to expose execution stages clearly

### 2. Middleware / tracing hooks
Already visible:
- `src/api/middleware/tracing.py`
- request ID propagation in `src/main.py`
- metrics in `src/core/monitoring.py`

Why it matters:
- harness systems are judged heavily on debuggability
- traceability is one of the easiest ways to make the project feel more production-grade

### 3. Retrieval-side observability potential
Already visible:
- rewrite
- hybrid retrieval
- rerank
- metrics around retrieval and generation latency

Why it matters:
- even before real tool execution, this gives a strong "observe → decide → continue" flavor

### 4. Experimental agent/workflow placeholders
Retained but currently downgraded:
- `src/agent/`
- `src/workflow/`
- `src/memory/`

Why it matters:
- these are useful as future expansion hooks
- but they should not be promoted as already production-ready

---

## What is still missing for a stronger Agent / Harness story

### P0 — must-have if you want to talk Agent / Harness credibly

#### A. Query / task router
Needed because:
- all requests should not be treated as the same kind of task
- execution systems need a decision layer before retrieval/generation

Target shape:
- knowledge lookup
- summarization/comparison
- action/tool candidate
- complex reasoning path

Status:
- **now added in lightweight form** via `src/core/query_router.py`

#### B. Structured execution trace
Needed because:
- harness systems need stage-level inspectability
- agent interviews often ask how you debug multi-step failures

Target shape:
- route decision
- rewrite stage
- retrieval stage
- rerank stage
- generation stage
- fallback triggered or not

Status:
- **now added in lightweight form** via `src/core/execution_trace.py`
- wired into `src/core/rag_engine.py`

#### C. Low-support fallback / abstain behavior
Needed because:
- one of the simplest markers of maturity is knowing when *not* to over-answer
- this is a core production safety pattern

Target shape:
- if retrieval returns nothing useful, return abstain / fallback metadata
- expose support confidence and reason

Status:
- **now added in lightweight form** in `src/core/rag_engine.py`

---

## P1 — highest-value next steps

### 1. Retrieval debug API or trace viewer payload
Suggested addition:
- add an endpoint or response option exposing:
  - route decision
  - rewritten queries
  - retrieved docs before/after rerank
  - stage latency

Why it helps:
- turns the project from a black box into a debuggable execution system

### 2. Tool-candidate execution envelope
Suggested addition:
- do not implement full tool use yet
- add a structured placeholder for tool candidates
- e.g. route returns `tool_candidate=true`, plus an execution policy note

Why it helps:
- lets you explain where harness logic would attach
- avoids fake tool support claims

### 3. Task-oriented evaluation
Suggested addition:
- beyond retrieval metrics, add:
  - route correctness (sampled/manual)
  - fallback correctness
  - trace completeness

Why it helps:
- harness roles care about system behavior, not only retrieval relevance

---

## P2 — valuable but only after P0/P1 are stable

### 1. Step-level state machine
Examples:
- planned
- retrieving
- reranking
- generating
- fallback
- complete
- error

### 2. Retry / timeout policy metadata
Expose:
- max attempts
- timed out stage
- fallback reason

### 3. Resume / interrupt hooks
Even if not fully implemented, a documented state model helps

### 4. Audit log model
Especially useful if later extending toward tool execution or enterprise workflows

---

## What should NOT be claimed yet

Do **not** claim this repo is already:

- a full agent harness
- a reliable tool-execution framework
- a multi-agent orchestration platform
- a production-grade workflow runtime
- a human-in-the-loop control plane

Those claims would currently be too easy to challenge.

---

## Recommended public positioning after current upgrades

### Safest positioning

> A production-oriented modular RAG system with lightweight query routing, structured execution traces, grounded answering fallback, and retrieval-side evaluation.

### If aiming slightly more Agent / Harness oriented

> A retrieval-augmented execution pipeline prototype that exposes task routing, stage-level traces, fallback behavior, and clear extension points toward tool/workflow orchestration.

That wording is much more defensible than saying "I built an agent framework".

---

## Resume-safe interpretation

What you can later say safely if the current direction is completed:

- Added a lightweight routing layer to distinguish lookup, summarization, and tool-candidate requests before retrieval/generation.
- Added structured execution traces across route / rewrite / retrieve / rerank / generate stages for debugging and evaluation.
- Added support-aware fallback behavior to avoid unsupported answers when retrieval evidence is insufficient.
- Kept the system retrieval-first and observable, while defining clear extension boundaries for future harness-style task execution.

---

## Immediate action plan

### Already in progress
- [x] lightweight query router
- [x] structured execution trace model
- [x] support / fallback metadata in core query path
- [x] API response extended with route / support / trace payloads
- [x] initial router unit tests

### Next recommended edits
- [ ] README rewrite to surface routing / trace / support
- [ ] ARCHITECTURE update to show decision boundary before retrieval
- [ ] ROADMAP update for harness-oriented extension path
- [ ] optional retrieval-debug endpoint or debug-response mode
- [ ] commit current repo changes

---

## Final recommendation

For Agent / Harness applications, do **not** abandon the RAG base.
Instead, make the project feel like:

- a **retrieval-backed execution system**
- with **routing**, **traceability**, **fallback**, and **evaluation**
- plus a clear boundary for future tool/workflow execution

That is much stronger than another generic "agent demo".
