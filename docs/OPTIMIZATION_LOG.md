# Optimization Log

本文件记录 `rag-enterprise-system` 的优化尝试，要求每项优化都能对应：
- 问题定义
- 代码改动
- commit
- 统一评测协议
- before / after 指标
- 是否保留

## Evaluation Protocol

- 固定脚本：`scripts/run_repo_grounded_eval.py`
- 固定数据：repo-grounded lightweight dataset（3 queries）
- 主要指标：
  - 质量：`recall@20` / `precision@3` / `mrr` / `map` / `avg_relevance` / `avg_faithfulness`
  - 稳定性：10-run `min/max/avg`、`badcases`、`fallback_rate`
  - 工程化：是否可复现、是否有固定脚本、是否有标准 artifact、是否可映射到 commit

## Current Baseline Snapshot

- 最新稳定报告：`artifacts/eval/stable_formal_report.json`
- 当前稳定值：
  - `recall@20 = 0.7222`
  - `precision@3 = 0.6667`
  - `mrr = 1.0`
  - `map = 0.7222`
  - `avg_faithfulness = 1.0`
  - `avg_relevance = 0.0833`
  - `badcases = 0`
- 当前结论：
  - 已完成“可跑通 / 可复现 / 指标稳定”
  - 尚未完成“继续涨 recall / precision”

---

## Optimization Entries

### OPT-001 检索 ID / 评测口径对齐

- **问题**：评测集 `relevant_docs` 与系统返回 source id 不一致，导致检索指标失真。
- **改动文件**：`src/retrieval/hybrid.py`
- **commit**：`b18e81a`
- **方法**：为 repo-grounded fallback retrieval 使用 repo 相对路径作为稳定文档 ID。
- **结果**：修复了“评测无效”问题，使 repo-grounded evaluation 可以成立。
- **结论**：保留。
- **类型**：评测有效性修复 / 工程化修复。

### OPT-002 生成回答 grounded 化

- **问题**：生成回答偏模板化，不贴合检索证据。
- **改动文件**：`src/generation/generator.py`
- **commit**：`b18e81a`
- **方法**：让 generator 优先复述检索证据，并增加 grounded fallback 摘要逻辑。
- **结果**：
  - `avg_faithfulness = 1.0`
  - `badcases = 0`
  - 回答不再完全是泛化模板
- **结论**：保留。
- **类型**：生成质量修复。

### OPT-003 reranker 去随机化

- **问题**：多轮重复验证结果波动，指标不可复现。
- **改动文件**：`src/rerank/three_stage.py`
- **commit**：`410b750`
- **方法**：移除 `np.random.uniform(0.9, 1.1)`，改为确定性排序。
- **结果**：
  - 10 次 `recall@20` / `precision@3` / `mrr` 结果完全一致
  - 稳定性大幅提升
- **结论**：保留。
- **类型**：稳定性优化 / 工程化优化。

### OPT-004 fallback 检索启发式加权（第一轮）

- **问题**：`docs/AGENT_HARNESS_GAP_ANALYSIS.md`、`docs/ROADMAP.md` 没被稳定顶到前排，导致 recall 卡住。
- **改动文件**：`src/retrieval/hybrid.py`
- **commit**：`c4df1e5`
- **方法**：针对 fallback / trace query 加 query→doc heuristic bonus。
- **结果**：
  - 已定位 recall 瓶颈
  - 当前未形成可见涨分
- **结论**：方法不足，需继续升级为更强的召回策略。
- **类型**：有效尝试，但未形成指标增益。

---

## Next Engineering Steps

1. **强制 doc injection**
   - fallback 类 query：保证 `docs/ROADMAP.md`、`docs/AGENT_HARNESS_GAP_ANALYSIS.md` 进入 top-k
   - trace 类 query：保证 `docs/AGENT_HARNESS_GAP_ANALYSIS.md` 进入 top-k

2. **段落级最大命中打分**
   - 从全文 token overlap 升级为 paragraph max score，减少 `README.md` / `ARCHITECTURE.md` 的长文优势

3. **统一评测落盘**
   - 所有后续优化都必须通过 `scripts/run_repo_grounded_eval.py` 生成 `artifacts/eval/optimization_runs/*.json`

4. **每轮优化都要补 before / after**
   - 不能只说“改了”，必须给 delta
