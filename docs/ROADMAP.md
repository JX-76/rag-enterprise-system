# ROADMAP

## 当前版本目标
把仓库整理为一个**面向 AI 大模型应用开发岗位**的模块化 RAG 项目，重点突出：

1. 检索质量优化
   - Parent-Child Chunking
   - Query Rewrite
   - Hybrid Retrieval
   - Reranking
2. AI 应用工程化
   - FastAPI API 层
   - Middleware / Logging / Metrics
   - 可运行、可调试、可解释的主链路
3. **RAG + 定向微调（Fine-tuning）演进方向**
   - 优先做**小模型 / 子模块级微调**，而不是空喊“大模型全量微调”
   - 重点考虑：Query Rewrite 小模型、Reranker / Embedding 适配、领域回答风格 SFT
   - 目标是让项目更贴近当前“RAG + 微调”岗位预期，同时保持可 defend

---

## 当前主打
- 文档解析与基础摄取
- Chunking
- Query Rewrite
- Hybrid Retrieval
- Rerank
- API 服务化封装
- 基础监控与中间件能力

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

## 下一步整理顺序
1. 收束重复目录
   - `src/document/` → `src/ingestion/`
   - `src/vector/` / `src/vector_store/` → 统一存储层
   - `src/rag/` 与 `src/retrieval/ + src/generation/ + src/core/` 边界进一步明确
2. 统一测试叙事
   - 正式测试以 `tests/` 为主
   - 根目录测试脚本降为兼容/辅助入口
3. 强化算法亮点表达
   - 补 trade-off
   - 补评估口径
   - 补 bad case 分析
4. 最终交付整理
   - 仓库首页
   - 架构文档
   - API 文档
   - Demo 路径

---

## 明确不做
当前版本**不追求**：
- 泛企业级大而全叙事
- 夸大的多租户/权限/生产级高可用承诺
- 无法 defend 的性能或线上能力表述

---

## 项目一句话概括
这是一个**模块化 RAG 项目**，我重点做了 **chunking / rewrite / hybrid retrieval / rerank** 等检索质量优化能力，并把它们通过 **FastAPI、中间件、日志和监控** 落成了一个可运行的 AI 应用系统。
