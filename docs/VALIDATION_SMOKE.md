# Validation Smoke Run

无服务版的 validation smoke 入口，用来快速确认：

- review 视图还能正常返回
- trace-summary 还能指出 slowest stage
- lightweight eval / badcases 还能正常出结构
- smoke 输出能稳定写进 `artifacts/eval/`

## 用法

```bash
python scripts/run_validation_smoke.py
```

## 输出

会生成以下文件：

- `artifacts/eval/smoke_review_output.json`
- `artifacts/eval/smoke_trace_output.json`
- `artifacts/eval/smoke_eval_output.json`
- `artifacts/eval/smoke_badcases_output.json`

## 适用场景

- 刚改完验证/调试接口后，先做冒烟
- 不想先起 uvicorn 时做结构确认
- 上传项目前再走一遍自检
