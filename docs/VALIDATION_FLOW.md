# Validation Flow

这份文档描述当前 RAG 项目的**轻量验证闭环**，目标不是给出最终对外指标，而是帮助你快速确认：

1. 主链路能跑通
2. support / fallback / trace 输出合理
3. badcase 能被捞出来
4. 每次验证结果能留档，便于迭代对照

---

## 1. 推荐验证顺序

### 第一步：启动服务

```bash
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

### 第二步：跑 lightweight eval

```bash
curl -X POST http://127.0.0.1:8000/api/v1/eval/lightweight \
  -H 'Content-Type: application/json' \
  -d @examples/lightweight_eval_request.json
```

预期：
- 返回 `meta.validation_level = lightweight`
- 返回 retrieval / generation / performance 三类汇总
- 自动在 `artifacts/eval/` 生成一份 JSON 结果

### 第三步：看 badcases

```bash
curl -X POST http://127.0.0.1:8000/api/v1/eval/badcases \
  -H 'Content-Type: application/json' \
  -d @examples/lightweight_eval_request.json
```

重点看：
- `badcase_count`
- `reasons`
- `support`
- `trace_id`

### 第四步：看单条 query 的 review 视图

```bash
curl -X POST http://127.0.0.1:8000/api/v1/query/review \
  -H 'Content-Type: application/json' \
  -d '{
    "query": "系统支持哪些检索优化能力？",
    "top_k": 5,
    "rewrite": true,
    "rerank": true
  }'
```

重点看：
- `route`
- `support`
- `top_sources`
- `suspicion_flags`

### 第五步：只看 trace 摘要

```bash
curl -X POST http://127.0.0.1:8000/api/v1/query/trace-summary \
  -H 'Content-Type: application/json' \
  -d '{
    "query": "当检索证据不足时系统会怎么处理？",
    "top_k": 5,
    "rewrite": true,
    "rerank": true
  }'
```

重点看：
- `slowest_stage`
- `fallback_triggered`
- `notes`

---

## 2. 怎么判断这轮验证有没有价值

### 可以接受的输出
- 能生成 artifact
- badcase 结构完整
- route / trace / support 字段齐全
- slowest_stage 能指出最慢阶段
- suspicion_flags 能提示低支持度或 fallback 风险

### 需要继续修的信号
- artifact 没写成功
- badcases 全空但明显有拒答/低支持度样本
- trace stages 缺字段
- review 视图看不出问题在哪
- 输出只有“能跑”，但没有可解释性

---

## 3. 当前定位

这套流程属于**轻量级验证**，适合：
- 本地 smoke run
- 每次结构改动后的快速确认
- 上传项目之前做一轮自检

它**不等于正式 benchmark**。

正式写进简历的数字，仍然要基于：
- 更完整的数据集
- 更稳定的测试轮次
- 更明确的对照基线

---

## 4. 建议搭配动作

- 每次改完 route / fallback / trace 逻辑，至少跑一轮 lightweight eval
- 每次输出 artifact 后，看一次 badcases
- 准备上传前，保留最近几轮 artifact 作为演进证据
