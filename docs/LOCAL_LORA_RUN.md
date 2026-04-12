# 本地 LoRA 训练说明

本文档用于说明如何在本地环境运行 Query Rewrite LoRA 训练。

## 1. 当前支持的两种模式

### 1.1 smoke-cpu
适用场景：
- 本地只有 CPU
- 先验证训练链路能不能跑通
- 不追求正式训练效果

特点：
- 使用超小模型
- step 很少
- 主要验证：数据读取、样本格式、LoRA 挂载、输出目录、训练入口

### 1.2 formal
适用场景：
- 有更强的本地环境或 GPU 环境
- 希望真正训练一个可评测的 LoRA 分支

特点：
- 默认面向 `Qwen/Qwen2.5-1.5B-Instruct`
- 更适合后续正式 baseline vs FT 对比

---

## 2. 安装训练依赖

```bash
pip install -r requirements-train.txt
```

如果你只是想先看配置是否正确，也可以不装完所有依赖，先跑 dry-run：

```bash
python scripts/train_rewrite_lora.py --dry-run
```

---

## 3. CPU Smoke Run

```bash
python scripts/train_rewrite_lora.py --profile smoke-cpu
```

默认行为：
- 使用 `sshleifer/tiny-gpt2`
- 使用小 batch
- 使用很少 step
- 输出到 `artifacts/ft/rewrite-lora-smoke`

### 建议预期
- 它的目标是**流程验证**，不是正式结果
- 如果本地 CPU 较弱，训练会慢一些，但应当能作为 smoke run 使用

---

## 4. Formal Run

```bash
python scripts/train_rewrite_lora.py \
  --profile formal \
  --model Qwen/Qwen2.5-1.5B-Instruct \
  --output-dir artifacts/ft/rewrite-lora-qwen
```

说明：
- 这一步更适合有 GPU 的环境
- 如果你本地只有 CPU，不建议直接跑 formal 配置

---

## 5. 常用命令

### 5.1 只检查配置和数据
```bash
python scripts/train_rewrite_lora.py --dry-run
```

### 5.2 本地 CPU 流程验证
```bash
python scripts/train_rewrite_lora.py --profile smoke-cpu
```

### 5.3 自定义输出目录
```bash
python scripts/train_rewrite_lora.py --profile smoke-cpu --output-dir artifacts/ft/my-smoke-run
```

### 5.4 正式训练（更强环境）
```bash
python scripts/train_rewrite_lora.py \
  --profile formal \
  --model Qwen/Qwen2.5-1.5B-Instruct \
  --epochs 3 \
  --batch-size 2 \
  --grad-accum-steps 4
```

---

## 6. 输出文件

训练脚本会生成：
- `run_config.json`：记录本次运行配置
- `train_summary.json`：记录训练完成状态（正式训练完成后）
- adapter / tokenizer 文件（实际训练成功后）

---

## 7. 当前数据集说明

当前默认使用：
- `data/ft/rewrite_train.jsonl`
- `data/ft/rewrite_dev.jsonl`
- `data/ft/rewrite_test.jsonl`

这些数据足够做：
- smoke run
- first-pass LoRA 流程验证

如果后续要做更有说服力的正式训练，建议继续扩充：
- train: 150+
- dev/test: 30+

---

## 8. 推荐工作流

### 当前最推荐的路线
1. 先跑 `--dry-run`
2. 再跑 `--profile smoke-cpu`
3. 确认输出目录和训练链路正常
4. 后续在 GPU 环境跑 `formal`
5. 最后结合 `scripts/eval_retrieval.py` 做 baseline vs FT 对比

---

## 9. 项目叙事建议

当前可以把这条线表述为：

> 项目已补齐 Query Rewrite LoRA 微调闭环，支持本地 CPU smoke run 与正式 LoRA 训练配置，并可进一步结合检索评测脚本进行 baseline vs FT variant 对照分析。
