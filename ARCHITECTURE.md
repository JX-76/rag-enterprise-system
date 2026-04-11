# Architecture Design

## 1. Design Goal

本项目的目标不是构建一个“什么都有”的企业级平台，而是围绕一条**完整、可解释、可扩展的 RAG 主链路**，验证以下能力：

1. **检索质量优化**：通过分块、查询改写、混合检索和重排提升回答质量。
2. **应用工程化落地**：通过 API 服务、配置管理、日志与监控，将算法链路落成可运行系统。
3. **模块化扩展能力**：保留替换向量库、Embedding 模型、Reranker 和 LLM 的空间。

这个定位更适合 AI 大模型应用开发岗位，也兼顾了一定的检索/算法方向亮点。

---

## 2. Core Pipeline

当前项目建议重点围绕以下主链路理解和演示：

```text
User Query
  -> Query Rewrite
  -> Hybrid Retrieval
  -> Reranking
  -> Context Construction
  -> LLM Generation
  -> Response with Sources
```

对于文档摄取链路：

```text
Document Ingestion
  -> Parsing
  -> Parent-Child Chunking
  -> Embedding / Indexing
  -> Retrieval Ready
```

---

## 3. Why This Pipeline

### 3.1 Parent-Child Chunking
- **问题**：固定窗口切块容易导致上下文被割裂。
- **做法**：用较小子块参与检索，用较大父块参与生成。
- **收益**：提高召回精度，同时保留更完整的生成上下文。

### 3.2 Query Rewriting
- **问题**：原始 query 可能过短、过模糊、信息不足。
- **做法**：对查询进行扩展、改写或生成多视角 query。
- **收益**：提升召回鲁棒性，尤其对复杂问题更有效。

### 3.3 Hybrid Retrieval
- **问题**：单一路径检索对不同查询类型覆盖不足。
- **做法**：结合 Dense、Sparse、BM25 等多路检索并进行融合。
- **收益**：提高召回多样性和命中概率。

### 3.4 Reranking
- **问题**：初始召回结果往往包含噪声或顺序不理想。
- **做法**：对候选结果进行分阶段过滤和排序。
- **收益**：为生成阶段提供更高质量上下文。

---

## 4. Logical Architecture

```text
┌───────────────────────────────────────────────┐
│ API Layer                                     │
│ FastAPI / Request Validation / Middleware     │
└───────────────────────┬───────────────────────┘
                        │
┌───────────────────────▼───────────────────────┐
│ RAG Orchestration                             │
│ Query Service / RAG Engine                    │
└───────────────────────┬───────────────────────┘
                        │
      ┌─────────────────┼─────────────────┐
      │                 │                 │
┌─────▼─────┐     ┌─────▼─────┐     ┌─────▼─────┐
│ Rewrite   │     │ Retrieval │     │ Rerank    │
│ Strategies│     │ Hybrid    │     │ MultiStage│
└─────┬─────┘     └─────┬─────┘     └─────┬─────┘
      │                 │                 │
      └─────────────────┼─────────────────┘
                        │
┌───────────────────────▼───────────────────────┐
│ Generation Layer                              │
│ Prompt Builder / LLM Generator                │
└───────────────────────┬───────────────────────┘
                        │
┌───────────────────────▼───────────────────────┐
│ Storage & Services                            │
│ Vector Store / Embedding / Cache / Metrics    │
└───────────────────────────────────────────────┘
```

---

## 5. Module Responsibilities

### 5.1 API Layer
职责：
- 暴露检索与问答接口
- 参数校验
- 请求级日志和追踪
- 统一错误处理

### 5.2 Core / Orchestration
职责：
- 串联 rewrite、retrieval、rerank、generation
- 作为项目主流程入口
- 控制不同模块开关与调用顺序

### 5.3 Ingestion
职责：
- 文档解析
- 分块
- 索引构建

### 5.4 Retrieval
职责：
- 查询改写
- 多路召回
- 结果融合

### 5.5 Rerank
职责：
- 候选文档精排
- 控制最终上下文质量和数量

### 5.6 Generation
职责：
- 构造 prompt
- 调用 LLM 生成回答
- 组织带来源的输出

### 5.7 Evaluation / Monitoring
职责：
- 记录 latency、结果数量等基础指标
- 预留 Recall@K / NDCG / MRR 等评估能力
- 支持 benchmark 和 bad case 分析

---

## 6. Current Scope

为了保证项目可信度，当前建议将能力划分为以下三层：

### Core Implemented
- 文档解析和基础摄取
- Parent-Child Chunking
- Hybrid Retrieval
- Query Rewrite（基础策略）
- Multi-stage Reranking
- FastAPI API 层
- 基础中间件能力（限流 / 熔断 / trace）
- 基础指标与监控

### Experimental
- Agentic RAG
- Hot Reload
- AB Testing
- Session-aware Rewrite 的进一步扩展
- Agent / Memory / Workflow 等探索模块
- 多租户与更细粒度权限模型的预研能力

> 说明：仓库中虽然仍保留 `src/tenancy/`、`src/ab_testing/`、`src/hot_reload/`、`src/agent/`、`src/memory/`、`src/workflow/`、`src/security/rbac.py` 等目录/模块，
> 但当前推荐理解方式是：**它们属于实验层或扩展层，不属于默认主调用路径，也不应作为首页主卖点。**

### Planned
- 更完整的多租户隔离
- 更严格的权限模型
- 更系统的线上评估闭环
- 更标准化的生产部署方案

---

## 7. Engineering Trade-offs

### 7.1 为什么不用“全都做深”的路线
对于公开技术项目而言，最大风险不是“能力少”，而是“宣称过大但讲不清”。

因此本项目采取的策略是：
- 把**检索质量优化**作为主线
- 把**应用工程化能力**作为支撑
- 把部分高级模块视为实验或扩展，而不是全部作为首页主卖点

### 7.2 为什么适合 AI 应用开发岗位
因为该项目不只是检索算法实验，还包含：
- API 服务化
- 模块化工程结构
- 配置和中间件设计
- 日志、监控、评估能力

这能更全面体现“把 LLM / RAG 能力落到真实系统”的能力。

---

## 8. Recommended Demo Path

建议按以下路径演示：

1. 文档如何被解析和切块
2. 查询如何被改写
3. hybrid retrieval 如何产生候选结果
4. rerank 前后候选结果如何变化
5. 最终如何基于上下文生成回答并返回引用来源
6. 项目中有哪些指标和工程能力帮助调试与优化

这样既能讲算法思路，也能讲工程落地。

---

## 9. Future Refactoring Direction

后续代码整理会优先沿这些方向进行：

1. 收束重复目录与重复入口
2. 统一 retrieval / generation / orchestration 的职责边界
3. 精简实验性模块在首页和主结构中的暴露程度
4. 增强评估与 benchmark 结果的解释性
5. 提升项目对“AI 应用开发 + 检索优化”岗位的针对性

---

## 10. Summary

这个项目的核心价值不在于“列出尽可能多的企业级模块”，而在于：

- 通过 **Chunking / Rewrite / Hybrid Retrieval / Rerank** 体现检索质量优化思路
- 通过 **FastAPI / Middleware / Metrics** 体现工程化能力
- 用一条完整且可解释的主链路，把算法模块和 AI 应用系统连接起来

这会比“大而全但不够聚焦”的项目形态更适合公开展示和技术交流。
