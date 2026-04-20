# MVP Checklist

基于当前第三视角评审结果，这份清单只保留**最能加速可信度建立**的动作。

## P0：立即执行

### 1. 固定最小可运行路径
目标：任何人拿到仓库后，能在最短路径内完成一轮自检。

步骤：
- `make smoke`
- 检查 `artifacts/eval/` 是否生成：
  - `smoke_review_output.json`
  - `smoke_trace_output.json`
  - `smoke_eval_output.json`
  - `smoke_badcases_output.json`
- 确认 review / trace / eval / badcases 四类结构完整

### 2. 固定最小评测集
目标：建立 repo-grounded、可检查、可复现的最小数据集。

当前数据集：
- `data/eval/repo_grounded_eval_v1.jsonl`
- 当前规模：30 条 query
- 已包含 category / difficulty / relevant_docs / answer_points

### 3. 固定 MVP 主卖点
对外统一只讲：
- retrieval quality optimization
- execution visibility
- API delivery

不要继续扩写：
- multi-agent
- workflow orchestration
- enterprise-grade multi-tenancy
- full production platform

---

## P1：下一步高 ROI 动作

### 4. 输出一份可 defend 的 EVAL_REPORT
至少包含：
- baseline 定义
- 数据集说明
- 质量指标
- 延迟指标
- badcases
- trade-off 说明

### 5. 建立 badcase 归因模板
每个 badcase 需要能归因到：
- rewrite miss
- retrieval miss
- rerank order issue
- insufficient support
- generation overreach

### 6. 建立分类评测视图
按 category 输出：
- recall / precision / mrr
- fallback rate
- badcase rate
- latency

---

## P2：展示增强

### 7. 做一页面试摘要
### 8. 做 5 分钟讲稿
### 9. 做 before / after 对比图

---

## 当前已完成

- README 口径收束
- API 口径收束
- 官方入口统一为 `src.main:app`
- `.gitignore` 已忽略 `artifacts/eval/`
- smoke 脚本可运行：`scripts/run_validation_smoke.py`
- `make smoke` / `make mvp-check` 已补入 Makefile
- repo-grounded eval 数据集已存在：`data/eval/repo_grounded_eval_v1.jsonl`

---

## 现在最重要的一句话

先把项目做成一个**可验证、可复现、可解释的 MVP**，再继续追求更完整的评测和更大的叙事。
