# Architecture Design - 架构设计文档

## 1. System Overview

### 1.1 Design Goals
- **高性能**: P99延迟<200ms，吞吐量1000+QPS
- **高质量**: Recall@20>88%，幻觉率<5%
- **高可用**: 99.9%可用性，自动故障恢复
- **可观测**: 全链路追踪，实时监控告警

### 1.2 Core Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         API Gateway                              │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐               │
│  │ Rate Limit  │ │   Tracing   │ │   Metrics   │               │
│  └─────────────┘ └─────────────┘ └─────────────┘               │
└────────────────────────────────┬────────────────────────────────┘
                                 │
┌────────────────────────────────▼────────────────────────────────┐
│                      Query Rewriter                              │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐          │
│  │   HyDE   │ │Multi-Query│ │Expansion │ │  Session │          │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘          │
└────────────────────────────────┬────────────────────────────────┘
                                 │
┌────────────────────────────────▼────────────────────────────────┐
│                    Hybrid Retrieval                              │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐                       │
│  │  Dense   │ │  Sparse  │ │  BM25    │                       │
│  │  40%     │ │  30%     │ │  30%     │                       │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘                       │
│       └─────────────┬─────────────┘                            │
│              ┌──────▼──────┐                                   │
│              │  RRF Fusion │                                   │
│              └─────────────┘                                   │
└────────────────────────────────┬────────────────────────────────┘
                                 │
┌────────────────────────────────▼────────────────────────────────┐
│                 Three-Stage Reranking                            │
│  Stage 1: BGE-small    │ Top100 → Top30 │ Lightweight           │
│  Stage 2: BGE-Reranker │ Top30 → Top10  │ Precise               │
│  Stage 3: Optimizer    │ Top10 → Top5   │ Generation-ready      │
└────────────────────────────────┬────────────────────────────────┘
                                 │
┌────────────────────────────────▼────────────────────────────────┐
│                     LLM Generation                               │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐               │
│  │   Context   │ │   Prompt    │ │Hallucination│               │
│  │ Compression │ │  Builder    │ │  Detection  │               │
│  └─────────────┘ └─────────────┘ └─────────────┘               │
└─────────────────────────────────────────────────────────────────┘
```

## 2. Module Details

### 2.1 Query Rewriting

#### HyDE (Hypothetical Document Embedding)
- **Purpose**: Generate hypothetical answer documents
- **Benefit**: Better semantic matching
- **Cost**: 1 LLM call per query

#### Multi-Query
- **Purpose**: Generate query variations
- **Benefit**: Improve recall
- **Cost**: N LLM calls per query

#### Query Expansion
- **Purpose**: Add synonyms
- **Benefit**: Better term matching
- **Cost**: Minimal

### 2.2 Retrieval Strategy

#### Dense Retrieval
- **Model**: BAAI/bge-large-zh-v1.5
- **Vector Store**: FAISS / Milvus
- **Similarity**: Cosine

#### Sparse Retrieval
- **Model**: SPLADE
- **Advantage**: Keyword matching
- **Use case**: Exact term retrieval

#### BM25
- **Library**: rank-bm25
- **Parameters**: k1=1.5, b=0.75
- **Use case**: Lexical matching

#### RRF Fusion
```python
score = Σ(1 / (k + rank))
k = 60 (constant)
```

### 2.3 Reranking Strategy

#### Stage 1: Lightweight Pre-ranking
- **Model**: BGE-small
- **Input**: 100 candidates
- **Output**: 30 candidates
- **Purpose**: Fast filtering

#### Stage 2: Precise Reranking
- **Model**: BGE-Reranker-large
- **Input**: 30 candidates
- **Output**: 10 candidates
- **Purpose**: Accurate relevance scoring

#### Stage 3: Generation Optimization
- **Deduplication**: Remove similar docs
- **Positioning**: High-relevance at position 1, 3
- **Length control**: Max 4000 tokens context

## 3. Data Flow

```
1. User Query
   ↓
2. Query Rewriting (HyDE + Multi-Query)
   ↓
3. Parallel Retrieval (Dense + Sparse + BM25)
   ↓
4. RRF Fusion
   ↓
5. Three-Stage Reranking
   ↓
6. Context Compression
   ↓
7. LLM Generation
   ↓
8. Hallucination Detection
   ↓
9. Response with Citations
```

## 4. Performance Optimization

### 4.1 Latency Optimization
- **Query Cache**: LRU + Redis
- **Async IO**: FastAPI + async/await
- **Parallel Execution**: asyncio.gather
- **Vector Index**: HNSW for fast search

### 4.2 Throughput Optimization
- **Batch Processing**: Batch encoding
- **Connection Pooling**: Vector DB connection reuse
- **Horizontal Scaling**: K8s HPA

### 4.3 Quality Optimization
- **Multi-route**: Combine dense + sparse + BM25
- **Reranking**: Three-stage for precision
- **HyDE**: Semantic query expansion

## 5. Deployment Architecture

```
                    ┌─────────────┐
                    │   Client    │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │  Ingress    │
                    │  Controller │
                    └──────┬──────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
   ┌────▼────┐       ┌────▼────┐       ┌────▼────┐
   │ API Pod │       │ API Pod │       │ API Pod │
   │ (HPA)   │       │ (HPA)   │       │ (HPA)   │
   └────┬────┘       └────┬────┘       └────┬────┘
        │                  │                  │
        └──────────────────┼──────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
   ┌────▼────┐       ┌────▼────┐       ┌────▼────┐
   │  Redis  │       │ Milvus  │       │Prometheus│
   │ (Cache) │       │(Vector) │       │(Metrics)│
   └─────────┘       └─────────┘       └─────────┘
```

## 6. Monitoring & Observability

### 6.1 Metrics
- **Latency**: P50, P95, P99
- **Throughput**: QPS
- **Quality**: Recall@K, NDCG
- **Errors**: Rate, Types

### 6.2 Logging
- **Structured**: JSON format
- **Tracing**: TraceID, SpanID
- **Correlation**: Request correlation

### 6.3 Alerting
- High latency (>1s)
- High error rate (>5%)
- Service unavailable

## 7. Security Considerations

- **Rate Limiting**: Token bucket algorithm
- **Circuit Breaker**: Prevent cascade failure
- **Input Validation**: Pydantic models
- **API Key**: Authentication (to be implemented)
