# Lightweight Evaluation Sample

用于快速验证 RAG 主链路、support/fallback 与 badcase 抽取能力的小样本数据。

## 用法

```bash
curl -X POST http://127.0.0.1:8000/api/v1/eval/lightweight \
  -H 'Content-Type: application/json' \
  -d @examples/lightweight_eval_request.json
```

或先查看原始样本：

```bash
cat examples/lightweight_eval_sample.json
```

## 说明

- 这是**轻量级验证集**，不是正式 benchmark。
- `relevant_docs` 仅用于方向性校验 Recall / MRR / NDCG 等指标。
- 默认会把结果写入 `artifacts/eval/`，便于保留每次验证记录。
- 正式对外结果应基于更完整的数据集与更长时间的实验。
