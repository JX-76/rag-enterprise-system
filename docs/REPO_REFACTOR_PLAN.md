# 仓库整改清单（面向公开技术展示与真实评测）

## 总体目标
将当前项目从“功能铺得很大、叙事不统一的 RAG 仓库”，整改为：

> 一个聚焦检索质量优化、兼顾工程落地、适合公开技术展示与检索优化实验的模块化 RAG 项目。

---

## 已完成（第一轮）
- 重写 README 首页叙事
- 重写 ARCHITECTURE 文档
- 明确项目定位：检索优化主线明确，工程落地路径清晰
- 加入模块成熟度分层：Core / Experimental / Planned

---

## 第二轮优先整改项

### 1. 统一项目入口
当前问题：
- `main.py`
- `src/main.py`
- `src/api/main.py`
- 多个 quickstart/demo 文件并存

整改建议：
- 仅保留一个正式 API 入口：`src/main.py`
- 根目录 `main.py` 改为轻量启动代理，或直接删除
- 所有 demo 统一迁移到 `examples/`
- 在 README 中明确“正式入口”和“演示入口”

优先级：高

---

### 2. 收束重复目录
当前问题：
- `src/document/` 与 `src/ingestion/` 职责重叠
- `src/vector/` 与 `src/vector_store/` 职责重叠
- `src/rag/` 与 `src/retrieval/ + src/generation/` 并行存在

整改建议：
- 将 `document/` 能力合并进 `ingestion/`
- 将 `vector/` 与 `vector_store/` 统一为单一向量存储层
- 将 `rag/` 中重复能力并入 `core/ + retrieval/ + generation/`
- 最终只保留一条主调用路径

优先级：高

---

### 3. 精简顶层噪音文件
当前问题：
顶层存在大量开发过程类文档，影响仓库专业感：
- `README_COMPLETE.md`
- `COMPLETION_REPORT.md`
- `REALITY_CHECK.md`
- `IMPLEMENTATION_NOTES.md`
- `COMMIT_REFACTOR.md`

整改建议：
- 保留：`README.md`、`ARCHITECTURE.md`、`API.md`、`DEPLOYMENT.md`、`CONTRIBUTING.md`
- 其余文档迁移到：`docs/archive/` 或 `docs/dev-notes/`

优先级：高

---

### 4. 模块成熟度降级处理
当前问题：
以下模块会显著抬高项目成熟度预期，但当前不适合作为首页主卖点：
- `tenancy/`
- `ab_testing/`
- `hot_reload/`
- `security/rbac.py`
- `agent/`
- `memory/`
- `workflow/`

整改建议：
- 从 README 首页主卖点移除
- 在文档中标注为 Experimental / Optional
- 代码层可保留，但从默认主链路中降权

优先级：高

---

### 5. 统一测试叙事
当前问题：
- 根目录存在大量 `test_*.py`
- `tests/` 目录内也有测试
- 测试入口混乱

整改建议：
- 所有正式测试统一放到 `tests/`
- 根目录 `test_all.py` 可以保留为聚合脚本，但不作为主测试组织方式
- `pytest` 作为标准测试入口
- 区分 unit / integration / benchmark

优先级：中高

---

## 第三轮整改项（偏工程可信度）

### 6. 修正 pyproject 元数据
当前问题：
- 作者是占位信息
- 仓库链接是占位链接
- 文档地址是占位链接

整改建议：
- 改成真实 GitHub 地址
- 补真实作者信息（或统一匿名形式）
- 让包元数据与仓库实际一致

优先级：高

---

### 7. 增强 API 角色说明
当前问题：
虽然 API 存在，但“为什么这些接口体现应用开发能力”讲得不够。

整改建议：
- 明确 Query API / Retrieve API / Health API 的角色
- 增加 retrieval-debug 类型的接口说明
- 让接口更像“可调试的 AI 应用系统”而不是只返回结果

优先级：中高

---

### 8. 补一份 ROADMAP
整改建议：
新增 `docs/ROADMAP.md`，明确：
- 当前版本重点
- 已实现能力
- 后续重构方向
- 不做什么

优先级：中

---

## 第四轮整改项（偏算法亮点表达）

### 9. 强化检索质量优化说明
整改建议：
针对以下模块补清楚设计意图与 trade-off：
- Parent-Child Chunking
- Hybrid Retrieval
- Query Rewrite
- Three-Stage Reranking

目标：
- 不只是“有这个模块”
- 而是“为什么设计、适合什么 query、代价是什么、收益是什么”

优先级：高

---

### 10. 评估口径明确化
整改建议：
补清楚项目如何评估：
- Recall@K
- NDCG / MRR
- latency
- bad case 分析
- retrieval / rerank 对效果的影响

优先级：中高

---

## 结构目标（目标状态）
希望最终结构更接近：

```text
src/
  api/
  core/
  ingestion/
  retrieval/
  rerank/
  generation/
  evaluation/
  services/
  storage/
  utils/
```

而不是当前的多套平行结构并存。

---

## 项目对外表述目标
整改后的项目应该能被总结为：

1. 这是一个**模块化 RAG 系统**，重点解决检索质量和工程落地问题。
2. 我重点做了 **query rewrite、hybrid retrieval、reranking、chunking** 等检索优化能力。
3. 我把这些算法模块通过 **FastAPI、中间件、日志、监控** 封装成了可运行的 AI 应用系统。

---

## 下一步建议执行顺序
1. 清理仓库顶层文档
2. 修正 `pyproject.toml`
3. 统一入口与 demo 说明
4. 收束重复目录
5. 明确主链路和 experimental 模块边界
6. 补评估与 benchmark 说明

---

## 备注
当前方向遵循用户要求：
- 目标表述：公开仓库保持中性技术叙事，突出检索优化与工程实现
- 风格：适度雄心，不做虚高叙事
- 策略：允许对不可信模块大胆降级或降权
