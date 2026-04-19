# 模块化 RAG 系统 - API 接口说明

本文档描述当前仓库**推荐对外使用的 API 入口与接口口径**。

为了避免历史实现和兼容路径造成理解混乱，先明确约定：

- **官方 API 入口**：`src.main:app`
- **兼容启动器**：根目录 `main.py`
- **推荐公开演示接口**：
  - `GET /health`
  - `GET /health/ready`
  - `POST /api/v1/retrieve`
  - `POST /api/v1/query`
  - `POST /api/v1/query/review`
  - `POST /api/v1/query/trace-summary`
  - `POST /api/v1/eval/lightweight`
  - `POST /api/v1/eval/badcases`

> 注意：仓库里保留了一些历史类、兼容路径和扩展示例。当前更推荐按 **retrieval-backed execution pipeline** 来理解 API，而不是按历史“全能力大一统 pipeline”去描述。

---

## 1. 启动方式

### 官方入口

```bash
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

### 兼容启动器

```bash
python main.py
```

### Swagger 文档

```text
http://127.0.0.1:8000/docs
```

---

## 2. 健康检查接口

### `GET /health`

用于检查服务是否存活。

**示例响应**

```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": 1710000000.0,
  "uptime": 12.34
}
```

### `GET /health/ready`

用于检查服务是否就绪。

**示例响应**

```json
{
  "ready": true,
  "checks": {
    "api": true,
    "cache": true,
    "vector_store": true
  }
}
```

---

## 3. 检索接口

### `POST /api/v1/retrieve`

只做检索，不做生成。适合：

- 检查召回质量
- 验证 rewrite / rerank 效果
- 做 retrieval 调试
- 分析 access-aware filtering 行为

### 请求体

```json
{
  "query": "系统支持哪些检索优化能力？",
  "top_k": 10,
  "rewrite": true,
  "rerank": true,
  "tenant_id": null,
  "role": null,
  "allowed_doc_ids": [],
  "metadata_filters": {}
}
```

### 主要字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| query | string | 用户查询 |
| top_k | int | 返回候选数量 |
| rewrite | bool | 是否启用查询改写 |
| rerank | bool | 是否启用重排序 |
| tenant_id | string \| null | 租户上下文 |
| role | string \| null | 角色信息 |
| allowed_doc_ids | string[] | 允许访问的文档 ID |
| metadata_filters | object | 额外元数据过滤条件 |

### 示例响应

```json
{
  "query": "系统支持哪些检索优化能力？",
  "results": [
    {
      "id": "doc_1",
      "content": "...",
      "score": 0.92,
      "metadata": {}
    }
  ],
  "request_id": "xxx",
  "latency_ms": 45.8,
  "access_context": {
    "tenant_id": null,
    "role": null,
    "allowed_doc_ids": [],
    "metadata_filters": {}
  }
}
```

---

## 4. 完整问答接口

### `POST /api/v1/query`

这是当前仓库的**主展示接口**。它会沿主链路执行：

1. Lightweight Query Routing
2. Query Rewrite（按配置启用）
3. Hybrid Retrieval
4. Multi-stage Reranking
5. Context Construction
6. LLM Generation
7. Support / Trace 输出

### 请求体

```json
{
  "query": "当检索证据不足时系统会怎么处理？",
  "conversation_id": null,
  "top_k": 5,
  "rewrite": true,
  "rerank": true,
  "stream": false,
  "tenant_id": null,
  "role": null,
  "allowed_doc_ids": [],
  "metadata_filters": {}
}
```

### 核心响应结构

```json
{
  "query": "当检索证据不足时系统会怎么处理？",
  "answer": "...",
  "sources": [],
  "rewritten_queries": [],
  "latency_ms": 123.4,
  "request_id": "xxx",
  "route": {
    "task_type": "qa",
    "route": "retrieve_then_generate",
    "confidence": 0.91,
    "reasons": ["..."],
    "rewrite_enabled": true,
    "rerank_enabled": true,
    "recommended_top_k": 5,
    "tool_candidate": false
  },
  "support": {
    "has_support": true,
    "confidence": 0.84,
    "reason": "...",
    "citations_count": 3
  },
  "trace": {
    "trace_id": "xxx",
    "route": {},
    "fallback_triggered": false,
    "notes": [],
    "stages": []
  }
}
```

### 为什么这个接口适合公开展示

因为它不仅返回最终答案，还显式暴露：

- `sources`：引用来源
- `route`：当前 query 是如何被路由的
- `support`：当前回答支撑度如何
- `trace`：链路各阶段发生了什么

这使它比“只回一段文本”的问答 demo 更适合：

- 调试
- 演示
- 面试讲解
- badcase 分析
- 后续评测和优化

---

## 5. 流式响应

当请求中设置：

```json
{
  "stream": true
}
```

`POST /api/v1/query` 会以 `text/event-stream` 方式返回。

适合：

- 前端实时展示生成过程
- 调试阶段事件流观测
- 演示 route / chunk / done 生命周期

---

## 6. Review 与 Trace Summary 接口

### `POST /api/v1/query/review`

输出适合**人工快速 review** 的视图。更适合：

- 看 route
- 看 support
- 看 top sources
- 看 suspicion flags
- 看当前 query 是否值得作为 badcase

### `POST /api/v1/query/trace-summary`

仅输出 trace 摘要，适合快速检查：

- 哪个阶段最慢
- route 是否符合预期
- 是否触发 fallback
- 当前链路是否异常

这两个接口是当前仓库很适合展示的“工程化可观测性”亮点。

---

## 7. 评测接口

### `POST /api/v1/eval/lightweight`

用于跑一轮轻量级方向性验证。

### 请求体

```json
{
  "dataset": [
    {
      "query": "系统支持哪些检索优化能力？",
      "relevant_docs": ["doc_1", "doc_2"]
    }
  ],
  "note": "smoke eval",
  "persist_artifact": true
}
```

### `POST /api/v1/eval/badcases`

用于提取 badcase，便于后续做：

- 错误分析
- 参数调优
- retrieval priors 调整
- prompt / rerank / fallback 收敛

### 关于评测结果的推荐表述

当前更建议把这些结果表述为：

- **lightweight validation**
- **directional signal**
- **debug / review artifacts**

而不是直接包装成“正式线上 benchmark 结论”。

---

## 8. 推荐演示调用顺序

如果你要 demo 这个系统，推荐按下面顺序调用：

1. `GET /health`
2. `POST /api/v1/retrieve`
3. `POST /api/v1/query`
4. `POST /api/v1/query/review`
5. `POST /api/v1/query/trace-summary`
6. `POST /api/v1/eval/lightweight`
7. `POST /api/v1/eval/badcases`

这样讲解最顺：

- 先证明服务活着
- 再证明能检索
- 再证明能回答
- 再证明能解释
- 最后证明能评测和找 badcase

---

## 9. 与历史类 / 旧路径的关系

仓库中仍有如下历史感较强的内容：

- `src/api/main.py`（历史入口）
- 部分旧的 `pipeline` / `memory` / `workflow` 示例
- 一些更偏探索性的类与接口说明

当前更推荐的理解方式是：

- **官方入口统一到 `src.main:app`**
- **公开演示以 query / retrieve / review / eval 这几组接口为主**
- **Memory / Workflow / Agent 相关能力视为扩展层，而非首页主打能力**

---

## 10. 总结

如果要用一句话描述当前 API 设计：

> 这套 API 的价值不只是“能回答问题”，而是把 **route / retrieval / rerank / support / trace / eval** 这些对于 RAG 工程真正重要的环节显式暴露出来。

这也是它适合作为一个 **modular, execution-oriented, retrieval-backed RAG repo** 来公开展示的原因。
