# Structure Guide

## Canonical vs Legacy Paths

为了兼顾当前仓库可运行性和面试可讲清楚性，项目采用如下理解方式：

### 建议按这些主路径理解项目（Canonical）
- `src/api/`：API 路由与中间件
- `src/core/`：主引擎、配置、日志、监控
- `src/ingestion/`：文档解析、分块、摄取流程
- `src/retrieval/`：检索与查询改写
- `src/rerank/`：重排
- `src/generation/`：生成
- `src/evaluation/`：评估
- `src/services/`：模型与 embedding 服务
- `src/utils/`：缓存、连接池等通用能力

### 当前保留但不建议作为主线理解（Legacy / Compatibility）
- `src/document/`
  - 与 `src/ingestion/` 职责重叠
  - 建议统一按 `src/ingestion/` 理解
- `src/vector/`
  - 与 `src/vector_store/` 职责重叠
  - 当前更推荐按 `src/vector_store/` 理解向量存储
- `src/rag/`
  - 含 pipeline / generator / query_rewriter 等历史聚合实现
  - 建议面试叙事中按 `core + retrieval + generation` 理解主链路
- `src/api/main.py`
  - 历史 FastAPI 入口
  - 官方 API 入口已收束为 `src.main:app`

---

## 当前收束策略

当前阶段优先做的是：
1. **文档收束**：README / ARCHITECTURE / API / ROADMAP 统一口径
2. **入口收束**：官方入口明确为 `src.main:app`
3. **演示路径收束**：示例统一到 `examples/`
4. **模块降权**：把实验性和历史模块从首页主卖点移除

而不是立即大规模删除目录。

这样做的原因：
- 避免一次性大改导致示例、测试、导入路径全部断裂
- 保留历史实现，方便回溯与渐进迁移
- 面试叙事先稳定，再做代码结构硬收束

---

## 后续真正代码级收束建议

### 1. document → ingestion
- 保留一个统一文档解析入口
- 测试与调用方逐步改到 `src/ingestion/`
- 最终把 `src/document/` 降为 compatibility layer 或归档

### 2. vector / vector_store → storage
- 统一成单一向量存储层
- 明确 FAISS / Milvus 各自角色
- 避免抽象层和实现层分散在两套目录

### 3. rag → orchestration
- 保留 pipeline 作为聚合入口时，建议明确它是 orchestration 层
- 避免与 retrieval / generation 的模块边界重复表达

---

## 面试时建议怎么说

推荐说法：

> 仓库里保留了一些历史目录和实验性实现，但当前我会按 ingestion / retrieval / rerank / generation / api 这条主线来解释项目。
> 也就是说，我先把“可讲清楚、可 defend 的主链路”定住，再逐步收束历史结构。
