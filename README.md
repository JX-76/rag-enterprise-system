# 模块化 RAG 系统（Modular RAG System）

> 一个面向 **检索优化、执行可观测性与工程落地** 的 production-oriented RAG 项目。
>
> 当前最适合公开展示的重点，不是“宣称什么都做完了”，而是：
> **把一条 retrieval-backed pipeline 讲清楚、跑起来、能解释、能评测。**

---

## 1. 项目定位

这个仓库聚焦的是一条 **可解释、可扩展、可工程化的 RAG 主链路**，重点解决三件事：

1. **检索质量优化**
   - 通过 chunking / rewrite / hybrid retrieval / rerank 提升召回与命中质量。
2. **执行边界与可观测性**
   - 通过 lightweight routing、structured trace、support-aware fallback，让链路更可解释、更可调试。
3. **工程化交付**
   - 通过 FastAPI、配置管理、日志、指标与评测接口，把方案落成一个可运行系统。

一句话概括：

> 这不是一个“什么能力都宣称成熟”的大而全 AI 平台，
> 而是一个 **围绕 retrieval quality + execution visibility + API delivery** 收束出来的模块化 RAG 项目。

---

## 2. 当前最适合对外强调的点

### 核心可展示能力（Core Implemented）

- **Parent-Child Chunking**：小块检索 + 大块生成，兼顾召回精度与上下文完整性
- **Hybrid Retrieval**：Dense / Sparse / BM25 多路检索融合
- **Query Rewriting**：对复杂、模糊 query 进行改写与扩展
- **Multi-stage Reranking**：多阶段候选过滤与精排
- **Lightweight Query Routing**：在主链路前做基础任务判断
- **Structured Execution Trace**：输出 route / retrieve / rerank / generate 的阶段化 trace
- **Support-aware Fallback**：证据不足时显式降级，而不是无依据强答
- **Lightweight Evaluation + Badcase Review**：支持快速方向性验证与问题样本抽取
- **FastAPI API Delivery**：提供统一 API 入口与调试接口

### 当前不建议过度宣称的点

下面这些能力在仓库里可能有探索、保留或扩展性尝试，但**不建议作为首页主卖点**：

- 完整多租户隔离
- 完整权限体系 / 企业级 ACL 闭环
- 完整 Agent Runtime / Harness
- 完整 Workflow Orchestration
- 成熟线上 A/B、自动回归、生产级运维闭环

更安全、更真实的公开表述应该是：

> **execution-oriented / harness-adjacent / retrieval-backed pipeline**
>
> 而不是“完整企业级 Agent 平台已经全部成熟”。

### 仓库说明（避免误读）

- **官方 API 入口**：`src.main:app`
- **当前主展示路由**：`src/api/routes/health.py`、`retrieval.py`、`query.py`、`evaluation.py`
- `src/api/routes.py` 为**早期单文件 demo 路由**，保留作参考，不作为当前对外主路径
- `docs/archive/` 中的模板、实验草稿和历史整理文档仅作归档，不代表当前主卖点已全部完成

---

## 3. 主链路（推荐演示口径）

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

如果从 execution 的视角理解，可以把它抽象成：

```text
Input
  -> Decide (route)
  -> Retrieve
  -> Refine
  -> Generate
  -> Fallback or Answer
  -> Trace / Audit
```

这条链路的价值不在“模块堆得多”，而在：

- **为什么这样检索** 能讲清楚
- **为什么这样降级** 能讲清楚
- **为什么这条路径可调试** 能讲清楚
- **为什么它能作为真实工程项目继续扩展** 也能讲清楚

---

## 4. 为什么不是 Naive RAG

相比“文档入库 -> 向量检索 -> 拼 Prompt -> 回答”的基础做法，这个项目重点补了四类增强：

### 4.1 Chunking
- 不直接依赖固定窗口切块
- 使用 Parent-Child 结构减少上下文割裂

### 4.2 Retrieval
- 不依赖单一路径召回
- 结合 Dense / Sparse / BM25 提升覆盖率

### 4.3 Rewrite
- 不把原始 query 原样扔给检索器
- 对复杂、模糊或信息不足的问题先改写，再检索

### 4.4 Rerank + Fallback + Trace
- 不把初始召回结果直接喂给生成
- 通过 rerank 提高上下文质量
- 通过 fallback 与 trace 提升可解释性和可靠性

---

## 5. 仓库成熟度分层

### Core Implemented

- 文档解析与基础摄取流程
- Parent-Child Chunking
- Hybrid Retrieval
- Query Rewriting（基础策略）
- Multi-stage Reranking
- Lightweight Query Routing
- Structured Execution Trace
- Support-aware Fallback
- FastAPI 查询 / 检索 / 评测接口
- 轻量级评测、badcase 提取与 review 视图
- 基础中间件能力（限流 / 熔断 / 请求追踪）
- 基础指标与监控

### Experimental / Optional

- Multi-Query / Session-Aware Rewrite 的更多策略
- Agentic RAG 相关尝试
- Hot Reload
- AB Testing
- Memory / Workflow 等扩展能力

> 仓库中保留的 `src/tenancy/`、`src/ab_testing/`、`src/hot_reload/`、`src/agent/`、`src/memory/`、`src/workflow/`、`src/security/rbac.py` 等目录 / 模块，
> 当前应理解为：**实验层、扩展层或历史保留层**，不是默认主调用路径。

### Planned

- retrieval-debug / debug mode
- 流式输出的进一步增强
- ACL / metadata-aware retrieval filtering 完善
- route correctness / fallback correctness 评测口径
- 更系统的 benchmark 与自动回归闭环
- 更清晰的 tool/workflow execution envelope

---

## 6. 快速开始（MVP 路径）

### 6.1 克隆仓库

```bash
git clone https://github.com/JX-76/rag-enterprise-system.git
cd rag-enterprise-system
```

### 6.2 安装最小依赖

如果你只是想先跑通一个 **MVP / Demo 版本**，优先安装：

```bash
pip install -r requirements-mvp.txt
```

如果你需要更完整的开发依赖，再安装：

```bash
pip install -r requirements.txt
```

### 6.3 启动依赖服务（可选）

```bash
docker-compose up -d
```

### 6.4 启动 API

**官方入口：**

```bash
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

**兼容启动器：**

```bash
python main.py
```

### 6.5 查看接口文档

```text
http://127.0.0.1:8000/docs
```

---

## 7. 最小演示方式

### 7.1 健康检查

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/health/ready
```

### 7.2 发起一次完整查询

```bash
curl -X POST http://127.0.0.1:8000/api/v1/query \
  -H 'Content-Type: application/json' \
  -d '{
    "query": "系统支持哪些检索优化能力？",
    "top_k": 5,
    "rewrite": true,
    "rerank": true
  }'
```

返回结果里除了答案，还会带：

- `sources`
- `route`
- `support`
- `trace`

这也是本项目相对普通问答 demo 更适合公开展示的地方。

### 7.3 查看 review / trace-summary 视图

```bash
curl -X POST http://127.0.0.1:8000/api/v1/query/review \
  -H 'Content-Type: application/json' \
  -d '{
    "query": "当检索证据不足时系统会怎么处理？",
    "top_k": 5,
    "rewrite": true,
    "rerank": true
  }'
```

```bash
curl -X POST http://127.0.0.1:8000/api/v1/query/trace-summary \
  -H 'Content-Type: application/json' \
  -d '{
    "query": "系统为什么要做 query routing？",
    "top_k": 5,
    "rewrite": true,
    "rerank": true
  }'
```

### 7.4 运行 lightweight eval / badcase 提取

```bash
curl -X POST http://127.0.0.1:8000/api/v1/eval/lightweight \
  -H 'Content-Type: application/json' \
  -d @examples/lightweight_eval_request.json
```

```bash
curl -X POST http://127.0.0.1:8000/api/v1/eval/badcases \
  -H 'Content-Type: application/json' \
  -d @examples/lightweight_eval_request.json
```

说明：

- 这些结果更适合作为 **方向性验证**，而不是正式对外 benchmark
- 默认结果会落到 `artifacts/eval/`
- 更适合拿来做调参、badcase 收敛和演示 review 闭环

---

## 8. 推荐公开演示 / 面试叙事

如果你要公开展示这个项目，建议按这条顺序讲：

1. **先讲问题**：Naive RAG 为什么不够
2. **再讲主链路**：routing -> rewrite -> retrieval -> rerank -> generate -> fallback -> trace
3. **再讲工程化**：FastAPI、日志、指标、评测接口
4. **最后讲边界**：哪些是 core，哪些是 experimental，哪些还在 roadmap

推荐一句话版本：

> 这是一个以 **retrieval quality + execution visibility + API delivery** 为主线的 modular RAG repo。
> 重点不是炫技，而是把主链路做得足够清楚、可运行、可解释、可继续迭代。

---

## 9. 项目结构（当前推荐理解方式）

```text
rag-enterprise-system/
├── src/
│   ├── api/                 # API 路由与中间件
│   ├── core/                # 主引擎、配置、日志、监控
│   ├── ingestion/           # 文档解析、分块、摄取流程
│   ├── retrieval/           # query rewrite / hybrid retrieval
│   ├── rerank/              # 重排
│   ├── generation/          # LLM 生成
│   ├── evaluation/          # 评估与指标
│   ├── services/            # 模型与 embedding 服务封装
│   └── utils/               # 缓存、连接池等通用能力
├── docs/                    # 补充文档
├── examples/                # Demo / lightweight eval 示例
├── artifacts/               # 评测与调试产物
├── tests/                   # 测试
└── README.md
```

更详细的 canonical / legacy 说明见：`docs/STRUCTURE_GUIDE.md`

---

## 10. 技术栈

- **API**：FastAPI
- **Embedding**：Sentence Transformers / BGE 系列
- **Retrieval**：Dense + Sparse + BM25
- **Rerank**：多阶段重排序
- **Vector Store**：FAISS / Milvus（模块化支持）
- **Cache / Middleware**：Redis / 自定义中间件
- **Monitoring / Eval**：Prometheus / 自定义评估模块
- **LLM 接入**：本地模型 / OpenAI-compatible API

---

## 11. 后续迭代方向

接下来更值得做的是：

1. 把 README / ARCHITECTURE / API 文档继续统一口径
2. 把评测结果解释、badcase 收敛和 benchmark 叙事继续磨清楚
3. 收束历史目录和兼容入口
4. 增强 retrieval-debug / review / trace 调试体验
5. 在不夸大能力的前提下，逐步补齐 execution-oriented 扩展

---

## 12. 总结

这个项目最值得展示的，不是“它像不像一个大而全企业平台”，而是：

- **一条完整且可解释的 RAG 主链路**
- **围绕检索质量优化的真实工程设计**
- **可观测、可调试、可评测的执行边界**
- **适合继续往 Agent / Harness 邻接方向扩展的结构基础**

如果你要一个更聚焦、更可信、也更适合公开展示的 RAG 项目，这个方向是对的。
