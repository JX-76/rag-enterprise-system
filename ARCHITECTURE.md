# Architecture Design

## 1. Design Goal

本项目当前的目标不是构建一个“什么都有”的企业级平台，而是围绕一条**完整、可解释、可扩展的 retrieval-backed execution pipeline**，验证以下能力：

1. **检索质量优化**：通过分块、查询改写、混合检索和重排提升回答质量。
2. **执行边界与可观测性**：通过 lightweight routing、structured trace、support-aware fallback 让链路更可解释、更可调试。
3. **应用工程化落地**：通过 API 服务、配置管理、日志与监控，将算法链路落成可运行系统。
4. **向 Agent / Harness 邻接扩展**：保留 task routing、tool-candidate execution 和 debug / audit 的扩展边界，但不夸大为完整 agent runtime。

这个定位强调的是：**主线清晰、执行边界明确、检索优化可解释、工程落地路径真实可 defend**。

---

## 2. Core Pipeline

当前项目建议重点围绕以下主链路理解和演示：

```text
Document Ingestion
  -> Parsing
  -> Parent-Child Chunking
  -> Embedding / Indexing

User Query
  -> Lightweight Query Routing
  -> Query Rewrite (conditional)
  -> Hybrid Retrieval
  -> Multi-stage Reranking
  -> Context Construction
  -> LLM Generation
  -> Response with Sources / Support / Trace
```

如果从 execution 角度理解，可抽象为：

```text
Input
  -> Decide (route)
  -> Retrieve
  -> Refine
  -> Generate
  -> Fallback or Answer
  -> Trace / Audit
```

---

## 3. Why This Pipeline

### 3.1 Parent-Child Chunking
- **问题**：固定窗口切块容易导致上下文被割裂。
- **做法**：用较小子块参与检索，用较大父块参与生成。
- **收益**：提高召回精度，同时保留更完整的生成上下文。

### 3.2 Lightweight Query Routing
- **问题**：所有请求都走同一条链路，会导致不必要的 rewrite、过度检索或错误的执行边界。
- **做法**：在主流程前增加轻量路由，对 exact lookup、summarization、complex reasoning、tool-candidate 请求进行基础区分。
- **收益**：增强执行可解释性，也为后续 task / tool 扩展保留边界。

### 3.3 Query Rewriting
- **问题**：原始 query 可能过短、过模糊、信息不足。
- **做法**：对查询进行扩展、改写或生成多视角 query。
- **收益**：提升召回鲁棒性，尤其对复杂问题更有效。

### 3.4 Hybrid Retrieval
- **问题**：单一路径检索对不同查询类型覆盖不足。
- **做法**：结合 Dense、Sparse、BM25 等多路检索并进行融合。
- **收益**：提高召回多样性和命中概率。

### 3.5 Multi-stage Reranking
- **问题**：初始召回结果往往包含噪声或顺序不理想。
- **做法**：对候选结果进行分阶段过滤和排序。
- **收益**：为生成阶段提供更高质量上下文。

### 3.6 Structured Trace + Support-aware Fallback
- **问题**：传统 RAG 经常只给最终答案，缺少中间可见性；检索证据不足时还可能强答。
- **做法**：输出 route / rewrite / retrieve / rerank / generate 的阶段级 trace，并在低支持度场景下返回明确 fallback。
- **收益**：增强系统调试性、演示性、评测可解释性和可靠性。

---

## 4. Logical Architecture

```text
┌──────────────────────────────────────────────────────────┐
│ API Layer                                                │
│ FastAPI / Request Validation / Middleware / Request ID   │
└───────────────────────────┬──────────────────────────────┘
                            │
┌───────────────────────────▼──────────────────────────────┐
│ Execution Boundary                                       │
│ Query Router / Request Classification / Route Metadata   │
└───────────────────────────┬──────────────────────────────┘
                            │
┌───────────────────────────▼──────────────────────────────┐
│ RAG Orchestration                                        │
│ RAG Engine / Stage Coordination / Trace Construction     │
└───────────────┬──────────────────────┬───────────────────┘
                │                      │
      ┌─────────▼─────────┐  ┌────────▼────────┐
      │ Retrieval Stack   │  │ Generation Stack│
      │ Rewrite           │  │ Prompt Builder  │
      │ Hybrid Retrieval  │  │ LLM Generator   │
      │ Reranking         │  │ Fallback        │
      └─────────┬─────────┘  └────────┬────────┘
                │                     │
                └─────────┬───────────┘
                          │
┌─────────────────────────▼────────────────────────────────┐
│ Response Layer                                           │
│ Answer / Sources / Support Signal / Structured Trace     │
└─────────────────────────┬────────────────────────────────┘
                          │
┌─────────────────────────▼────────────────────────────────┐
│ Storage & Services                                        │
│ Vector Store / Embedding / Cache / Metrics / Logs         │
└───────────────────────────────────────────────────────────┘
```

---

## 5. Module Responsibilities

### 5.1 API Layer
职责：
- 暴露检索与问答接口
- 参数校验
- 请求级日志和追踪
- 统一错误处理
- 为后续流式输出和调试视图保留接口边界

### 5.2 Execution Boundary
职责：
- 在主链路前进行轻量任务判断
- 给出 route decision、建议 top-k、rewrite/rerank 开关
- 区分知识问答与 tool-candidate 请求
- 为未来 harness-style execution 扩展提供接入点

### 5.3 Core / Orchestration
职责：
- 串联 route、rewrite、retrieval、rerank、generation
- 构建统一 execution trace
- 管理 fallback 逻辑
- 作为项目主流程入口

### 5.4 Ingestion
职责：
- 文档解析
- 分块
- 索引构建
- 为后续 metadata / ACL 过滤保留结构化元数据

### 5.5 Retrieval
职责：
- 查询改写
- 多路召回
- 结果融合
- 为后续 retrieval-debug / metadata filtering 提供基础

### 5.6 Rerank
职责：
- 候选文档精排
- 控制最终上下文质量和数量
- 服务于生成质量与上下文长度 trade-off

### 5.7 Generation
职责：
- 构造 prompt
- 调用 LLM 生成回答
- 在证据不足或模型异常时做降级处理
- 组织带来源、support 和 trace 的输出

### 5.8 Evaluation / Monitoring
职责：
- 记录 latency、结果数量等基础指标
- 预留 Recall@K / NDCG / MRR 等评估能力
- 支持 benchmark、bad case 与 route/fallback 分析

---

## 6. Current Scope

为了保证项目可信度，当前建议将能力划分为以下三层：

### Core Implemented
- 文档解析和基础摄取
- Parent-Child Chunking
- Hybrid Retrieval
- Query Rewrite（基础策略）
- Multi-stage Reranking
- Lightweight Query Routing
- Structured Execution Trace
- Support-aware Fallback
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
- 更强的 tool execution / workflow orchestration

> 说明：仓库中虽然仍保留 `src/tenancy/`、`src/ab_testing/`、`src/hot_reload/`、`src/agent/`、`src/memory/`、`src/workflow/`、`src/security/rbac.py` 等目录/模块，
> 但当前推荐理解方式是：**它们属于实验层或扩展层，不属于默认主调用路径，也不应作为首页主卖点。**

### Planned
- retrieval-debug / debug mode
- 流式输出接口
- ACL / metadata-aware retrieval filtering
- route correctness / fallback correctness 评测口径
- tool-candidate execution envelope
- 更系统的线上评估闭环

---

## 7. Engineering Trade-offs

### 7.1 为什么不用“全都做深”的路线
对于公开技术项目而言，最大风险不是“能力少”，而是“宣称过大但讲不清”。

因此本项目采取的策略是：
- 把**检索质量优化**作为主线
- 把**执行可观测性**作为升级点
- 把**应用工程化能力**作为支撑
- 把部分高级模块视为实验或扩展，而不是全部作为首页主卖点

### 7.2 为什么这条路线适合 Agent / Harness 邻接叙事
因为该项目不只是检索算法实验，还开始具备：
- query routing
- execution trace
- fallback behavior
- 可扩展的 tool-candidate 边界

这意味着它已经不只是“问答 demo”，而是在向**retrieval-backed execution system** 靠近。

### 7.3 为什么暂时不直接宣称完整 harness
因为当前仓库还缺：
- 稳定 tool execution
- retry / rollback / timeout 策略
- state machine
- audit log / interrupt / resume 机制

所以更安全的公开说法应该是：
**harness-adjacent / execution-oriented / retrieval-backed pipeline**，而不是“完整 agent framework”。

---

## 8. Recommended Demo Path

建议按以下路径演示：

1. 文档如何被解析和切块
2. 查询如何先经过 routing decision
3. rewrite 是否被启用，以及为什么启用
4. hybrid retrieval 如何产生候选结果
5. rerank 前后候选结果如何变化
6. 最终如何基于上下文生成回答并返回引用来源
7. 低支持度场景下如何 fallback
8. trace 和指标如何帮助调试与优化

这样既能讲检索思路，也能讲 execution boundary 和工程落地。

---

## 9. Future Refactoring Direction

后续代码整理会优先沿这些方向进行：

1. 收束重复目录与重复入口
2. 统一 retrieval / generation / orchestration 的职责边界
3. 精简实验性模块在首页和主结构中的暴露程度
4. 增强评估、trace 和 benchmark 结果的解释性
5. 增加流式输出、ACL / metadata filtering、debug 视图等高性价比能力
6. 提升项目对“AI 应用系统 + retrieval-backed execution”叙事的聚焦度

---

## 10. Summary

这个项目的核心价值不在于“列出尽可能多的企业级模块”，而在于：

- 通过 **Chunking / Routing / Rewrite / Hybrid Retrieval / Rerank** 体现检索增强思路
- 通过 **Trace / Support-aware Fallback** 体现执行可观测性与可靠性
- 通过 **FastAPI / Middleware / Metrics** 体现工程化能力
- 用一条完整且可解释的主链路，把检索模块和 execution-oriented AI application 连接起来

这会比“大而全但不够聚焦”的项目形态更适合公开展示、简历叙事和技术面试。
