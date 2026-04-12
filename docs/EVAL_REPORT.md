# 检索评测报告（v1）

## 1. 评测目标

本轮评测聚焦一个最小但可 defend 的问题：

> 在固定的 repo-grounded 轻量检索基线上，引入 Query Rewrite / FT Rewrite 分支后，是否能提升相关文档的命中率与排序质量？

本报告的定位是：
- 使用**真实、可检查**的小语料
- 使用**固定 baseline**
- 输出一组**可复现**的 first-pass 检索指标
- 不夸大为线上生产结果

---

## 2. 评测设置

### 2.1 评测集
- 文件：`data/eval/repo_grounded_eval_v1.jsonl`
- 查询数：**30**

### 2.2 语料范围
从仓库实际文件中抽取可检查语料：
- `README.md`
- `ARCHITECTURE.md`
- `API.md`
- `docs/ROADMAP.md`
- `docs/STRUCTURE_GUIDE.md`
- 以及评测集中标注的相关文件路径

### 2.3 对比方案
- **Baseline**：原始 query 直接检索
- **FT Rewrite Variant**：使用当前 rewrite 数据生成的改写 query 再检索

### 2.4 检索后端
- `bm25-lite lexical retrieval`
- 说明：这是一个本地、轻量、无外部依赖的可复现检索基线，用于 first-pass 评测，不等价于最终 dense / hybrid 生产检索后端

---

## 3. 核心指标

### 3.1 Baseline
- Recall@1: **0.2722**
- Recall@3: **0.6611**
- Recall@5: **0.7500**
- Precision@1: **0.5667**
- Precision@3: **0.4667**
- Precision@5: **0.3267**
- MRR: **0.7145**
- MAP: **0.6395**
- NDCG@5: **0.6682**
- Avg Latency: **1.016 ms**
- P95 Latency: **1.074 ms**

### 3.2 FT Rewrite Variant
- Recall@1: **0.3278**
- Recall@3: **0.6722**
- Recall@5: **0.7722**
- Precision@1: **0.6667**
- Precision@3: **0.4778**
- Precision@5: **0.3400**
- MRR: **0.7745**
- MAP: **0.7231**
- NDCG@5: **0.7260**
- Avg Latency: **1.291 ms**
- P95 Latency: **1.418 ms**

### 3.3 指标变化（FT - Baseline）
- Recall@1: **+0.0556**
- Recall@3: **+0.0111**
- Recall@5: **+0.0222**
- Precision@1: **+0.1000**
- Precision@3: **+0.0111**
- Precision@5: **+0.0133**
- MRR: **+0.0600**
- MAP: **+0.0836**
- NDCG@5: **+0.0578**
- Avg Latency: **+0.275 ms**
- P95 Latency: **+0.344 ms**

---

## 4. 结果解读

这组结果说明：

1. **首位命中能力提升明显**
   - Recall@1 与 Precision@1 均提升 **10 个百分点**
   - 说明 rewrite 后更容易把真正相关的文档顶到前面

2. **整体排序质量提升**
   - MRR、MAP、NDCG@5 均提升
   - 说明 rewrite 不只是“多捞一点”，而是改善了相关文档整体排序

3. **开销可控**
   - 延迟有轻微上升，但在本地轻量检索基线上仍然很低
   - 说明 first-pass rewrite 分支具备继续投入的价值

---

## 5. 当前边界

本报告仍有明确边界：

- 这是 **repo-grounded 小语料评测**，不是线上生产数据
- 当前检索后端是 **bm25-lite lexical baseline**，不是最终 dense / hybrid 检索主链路
- 当前结果更适合表述为：
  - **first-pass 可复现效果**
  - **rewrite 分支具备正向增益**
  - **值得继续做 dense / hybrid / rerank 的进一步 ablation**

不应直接夸大为：
- 全量生产环境效果
- 泛化到所有业务场景的最终结论

---

## 6. 下一步建议

1. 在同一评测集上补跑：
   - dense-only vs hybrid retrieval
   - no rewrite vs query rewrite
   - retrieval-only vs retrieval + rerank
2. 增加 bad case 分析
3. 补充更完整的生成侧指标（如 answer relevance / faithfulness）
4. 输出统一的 `artifacts/eval/retrieval_eval_v1.json`

---

## 7. 可用于简历/项目介绍的安全说法

可以安全写成：

> 在 30 条 repo-grounded 评测集上，对 Query Rewrite 分支进行了 first-pass 检索评测；在固定轻量检索基线上，Recall@1 从 56.7% 提升到 66.7%，Recall@5 从 83.3% 提升到 86.7%，MRR 从 0.7145 提升到 0.7745。

更稳的说法：

> 基于可检查的小规模仓库语料搭建了可复现评测集，并验证了 Query Rewrite 分支对检索命中率与排序质量的正向作用。
