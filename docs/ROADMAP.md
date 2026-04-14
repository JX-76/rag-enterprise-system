# ROADMAP

## 当前版本目标
把仓库整理为一个**聚焦检索质量优化、执行可观测性与工程落地**的 modular RAG 项目，重点突出：

1. 检索质量优化
   - Parent-Child Chunking
   - Query Rewrite
   - Hybrid Retrieval
   - Reranking
2. 执行边界与可观测性
   - Lightweight Query Routing
   - Structured Execution Trace
   - Support-aware Fallback
   - 可扩展的 debug / retrieval inspection 视图
3. AI 应用工程化
   - FastAPI API 层
   - Middleware / Logging / Metrics
   - 可运行、可调试、可解释的主链路
4. **RAG + 定向微调（Fine-tuning）演进方向**
   - 优先做**小模型 / 子模块级微调**，而不是空喊“大模型全量微调”
   - 对于接入的**大模型链路**，默认要求至少配一条**轻量、可解释、可评测的微调分支**，优先选择 Query Rewrite、Reranker 或 Embedding 适配
   - 重点考虑：Query Rewrite 小模型、Reranker / Embedding 适配、领域回答风格 SFT
   - 目标是在不夸大能力的前提下，为项目补上一条真实、轻量、可解释的 FT 演进路径

---

## 当前主打
- 文档解析与基础摄取
- Chunking
- Query Routing
- Query Rewrite
- Hybrid Retrieval
- Rerank
- Support-aware answer fallback
- API 服务化封装
- 基础监控与中间件能力
- 请求级 / 阶段级 trace 元数据

---

## 当前保留但降权
以下目录/模块保留在仓库中，但不作为首页主卖点：

- `src/tenancy/`
- `src/ab_testing/`
- `src/hot_reload/`
- `src/agent/`
- `src/memory/`
- `src/workflow/`
- `src/security/rbac.py`

这些内容更适合作为：
- 实验性探索
- 扩展预留
- 历史实现痕迹

---

## Agent / Harness 邻接扩展路径
当前版本不直接把自己包装成“完整 agent framework”，而是先补齐以下能力，为后续扩展保留清晰边界：

### P0：已开始 / 应尽快稳定
- Lightweight Query Router
- Structured Execution Trace
- Support-aware Fallback
- API 响应中显式返回 route / support / trace

### P1：下一阶段建议补齐
- retrieval-debug / debug mode
- route correctness / fallback correctness 评测口径
- tool-candidate execution envelope（占位而不夸大）
- 更细化的 stage-level state 与失败原因分类

### P2：后续再考虑
- tool execution policy
- retry / timeout / rollback 策略
- interrupt / resume hooks
- audit log model

---

## 下一步整理顺序
1. 收束公开叙事
   - README
   - ARCHITECTURE
   - ROADMAP
   - API 文档
2. 收束重复目录
   - `src/document/` → `src/ingestion/`
   - `src/vector/` / `src/vector_store/` → 统一存储层
   - `src/rag/` 与 `src/retrieval/ + src/generation/ + src/core/` 边界进一步明确
3. 统一测试叙事
   - 正式测试以 `tests/` 为主
   - 根目录测试脚本降为兼容/辅助入口
4. 强化算法和执行亮点表达
   - 补 trade-off
   - 补评估口径
   - 补 bad case 分析
   - 补 route / trace / fallback 的 public-safe 说法
5. 最终交付整理
   - 仓库首页
   - 架构文档
   - API 文档
   - Demo 路径
   - Debug / Evaluation 说明

---

## 明确不做
当前版本**不追求**：
- 泛企业级大而全叙事
- 夸大的多租户/权限/生产级高可用承诺
- 无法 defend 的性能或线上能力表述
- 未实现却包装成成熟的 multi-agent / harness runtime

---

## 项目一句话概括
这是一个**production-oriented modular RAG 项目**，我重点做了 **routing / rewrite / hybrid retrieval / rerank / trace / support-aware fallback** 等能力，并把它们通过 **FastAPI、中间件、日志和监控** 落成了一个可运行、可调试、可继续向 Agent / Harness 方向扩展的 AI 应用系统。
