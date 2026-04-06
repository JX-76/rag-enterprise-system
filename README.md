# RAG Enterprise System

> 企业级RAG系统核心模块实现 - 学习/教学项目

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

⚠️ **重要声明**: 本项目是**学习性质**的RAG系统实现，包含部分核心模块的完整代码，但**不是可直接部署的生产系统**。详见 [REALITY_CHECK.md](REALITY_CHECK.md)

---

## 🎯 项目定位

本项目是为了**深入理解企业级RAG架构**而开发的**学习项目**，特点：

- ✅ **完整实现**: 熔断器、限流器、父子分块、评估指标（有单元测试）
- ⚠️ **部分实现**: 检索、重排（结构完整，使用模拟数据演示）
- ❌ **尚未实现**: 文档解析、向量化入库、端到端Pipeline

**适合人群**:
- 想理解RAG架构设计的工程师
- 准备面试需要项目谈资的求职者
- 学习生产级代码组织的开发者

**不适合**:
- 寻找开箱即用的RAG产品的用户
- 需要完整生产系统的团队

---

## ✅ 完整实现的模块

### 1. 熔断器 (Circuit Breaker)

```python
from src.api.middleware.circuit_breaker import CircuitBreaker, CircuitBreakerConfig, CircuitState

# 创建熔断器
config = CircuitBreakerConfig(
    failure_threshold=3,
    recovery_timeout=30.0,
    success_threshold=2
)
breaker = CircuitBreaker("vector_db", config)

# 使用
try:
    result = await breaker.call(query_database, param)
except CircuitBreakerOpen:
    # 熔断时的降级处理
    return cached_result
```

**状态机**: CLOSED → OPEN → HALF_OPEN → CLOSED  
**测试**: `python -m pytest tests/unit/test_circuit_breaker.py -v`  
**实现文件**: `src/api/middleware/circuit_breaker.py` (400+行，含HALF_OPEN恢复逻辑)

### 2. 限流器 (Rate Limiter)

```python
from src.api.middleware.rate_limit import TokenBucket

# 创建限流器: 10 token/秒, 容量20
bucket = TokenBucket(rate=10, capacity=20)

# 获取许可
if await bucket.acquire():
    # 处理请求
    pass
else:
    # 限流拒绝
    return {"error": "Rate limit exceeded"}
```

**算法**: Token Bucket (支持突发流量)  
**测试**: `python -m pytest tests/unit/test_rate_limit.py -v`  
**实现文件**: `src/api/middleware/rate_limit.py`

### 3. 父子分块 (Parent-Child Chunking)

```python
from src.ingestion.parent_child_chunker import ParentChildChunker

chunker = ParentChildChunker(
    parent_size=1000,   # 父块1000 tokens
    child_size=200,     # 子块200 tokens
    child_overlap=40    # 20%重叠
)

chunks = chunker.chunk(text)
# 返回: List[ParentChunk]
# 每个ParentChunk包含多个ChildChunk
# 检索时匹配子块，返回父块作为上下文
```

**优势**:
- 子块小 → 检索精度高
- 父块大 → 上下文完整

**测试**: `python -m pytest tests/unit/test_parent_child_chunker.py -v`  
**实现文件**: `src/ingestion/parent_child_chunker.py` (420+行)

### 4. 评估指标 (Evaluation Metrics)

```python
from src.evaluation.metrics import RetrievalEvaluator, RetrievalMetrics

evaluator = RetrievalEvaluator()
metrics = evaluator.evaluate(
    queries=queries,
    retrieved_results=results,
    ground_truth=ground_truth
)

print(f"Recall@5: {metrics.recall_at_k[5]}")
print(f"MRR: {metrics.mrr}")
print(f"NDCG@5: {metrics.ndcg_at_k[5]}")
```

**支持指标**: Recall@K, Precision@K, MRR, MAP, NDCG@K  
**实现文件**: `src/evaluation/metrics.py`

---

## ⚠️ 部分实现的模块

这些模块有完整代码结构，但使用模拟数据进行演示：

| 模块 | 状态 | 说明 |
|------|------|------|
| 混合检索 | ⚠️ 骨架 | RRF融合逻辑完整，但向量检索为Mock |
| 三阶重排 | ⚠️ 骨架 | 结构完整，使用模拟分数演示流程 |
| 查询改写 | ⚠️ 骨架 | 接口定义完整，无真实LLM调用 |

---

## 🚀 快速开始

### 环境要求

- Python 3.9+
- 无需GPU
- 无需Docker

### 安装

```bash
# 克隆项目
git clone https://github.com/JX-76/rag-enterprise-system.git
cd rag-enterprise-system

# 安装依赖
pip install -r requirements.txt
```

### 运行测试

```bash
# 测试熔断器
python -m pytest tests/unit/test_circuit_breaker.py -v

# 测试限流器  
python -m pytest tests/unit/test_rate_limit.py -v

# 测试父子分块
python -m pytest tests/unit/test_parent_child_chunker.py -v

# 运行所有测试
python -m pytest tests/unit/ -v
```

### 运行演示

```bash
# 模块功能演示（真实代码运行）
python quickstart.py
```

输出示例：
```
======================================================================
  RAG Enterprise System - Module Tests
  核心模块功能验证
======================================================================

[1/4] 熔断器测试
  ✓ 初始状态: CLOSED
  ✓ 3次失败后状态: OPEN (熔断触发)
  ✓ 30秒后进入: HALF_OPEN
  ✓ 2次成功后恢复: CLOSED
  → 熔断器状态机工作正常

[2/4] 限流器测试
  ✓ 10 token/s 配置
  ✓ 15次请求中10次通过，5次被拒绝
  → Token Bucket限流工作正常

[3/4] 父子分块测试
  ✓ 10000字符文本分块
  ✓ 生成12个父块，48个子块
  ✓ 子块与父块关联正确
  → Parent-Child分块工作正常

[4/4] 评估指标测试
  ✓ Recall@5 计算正确
  ✓ MRR 计算正确
  ✓ NDCG@5 计算正确
  → 评估指标计算正确

======================================================================
  ✅ 所有模块测试通过！
======================================================================
```

---

## 📁 项目结构

```
rag-enterprise-system/
├── src/                              # 源代码
│   ├── api/                          # FastAPI接口
│   │   ├── middleware/               # 中间件
│   │   │   ├── circuit_breaker.py    # ✅ 熔断器 (完整实现)
│   │   │   └── rate_limit.py         # ✅ 限流器 (完整实现)
│   │   └── routes/                   # 路由 (骨架)
│   ├── ingestion/                    # 数据接入
│   │   └── parent_child_chunker.py   # ✅ 父子分块 (完整实现)
│   ├── evaluation/                   # 评估模块
│   │   └── metrics.py                # ✅ 评估指标 (完整实现)
│   ├── retrieval/                    # 检索模块 (骨架)
│   └── rerank/                       # 重排模块 (骨架)
├── tests/                            # 测试
│   └── unit/                         # 单元测试
│       ├── test_circuit_breaker.py   # ✅ 熔断器测试
│       ├── test_rate_limit.py        # ✅ 限流器测试
│       └── test_parent_child_chunker.py  # ✅ 分块测试
├── scripts/                          # 脚本
│   ├── run_experiments.py            # 实验框架
│   ├── text_visualize.py             # 文本可视化
│   └── download_arxiv.py             # 数据下载
├── blog/                             # 技术博客
│   └── 01-circuit-breaker-rate-limit.md  # 熔断限流详解
├── README.md                         # 本文件
├── REALITY_CHECK.md                  # 项目真实状态检查
└── requirements.txt                  # 依赖
```

---

## 🧪 实验框架

支持对比实验，记录迭代过程：

```bash
# 运行实验（使用模拟数据演示框架）
python scripts/run_experiments.py --experiment chunk_size

# 可视化结果
python scripts/text_visualize.py --input experiments/*.json
```

实验框架特点：
- 支持不同策略的对比
- 自动计算Recall@K, MRR, NDCG
- 生成可视化报告

**注意**: 当前使用模拟数据演示框架，真实数据需要补充文档解析和向量化模块。

---

## 📚 技术博客

| 文章 | 内容 | 状态 |
|------|------|------|
| [01. 熔断与限流](blog/01-circuit-breaker-rate-limit.md) | 生产环境稳定性设计 | ✅ 已发布 |

博客特点：
- 基于真实代码讲解
- 包含面试可谈的细节
- 不夸大，不虚构

---

## 📝 面试谈资（诚实版）

**可以这样说**:

> "我为了深入理解RAG系统架构，独立实现了几个核心生产级模块：
> 
> 1. **熔断器**: 实现了CLOSED/OPEN/HALF_OPEN三态状态机，包含自动恢复逻辑。代码400+行，有完整单元测试。
> 2. **父子分块**: 实现了滑动窗口+语义边界识别，解决分块上下文断裂问题。代码420+行。
> 3. **评估框架**: 实现了Recall@K, MRR, NDCG等检索指标计算。
> 
> 目前还是模块级别的实现，正在补齐文档解析和向量化链路。项目代码在GitHub上，核心模块有完整单元测试。"

**绝对不要说**:

> ❌ "我做了一个企业级RAG系统，支持1000 QPS"
> ❌ "我的系统Recall@5达到88%"
> ❌ "可直接部署生产环境"

---

## 🔧 补全计划

如果你想把项目变成完整可运行的RAG系统：

### Phase 1: 补齐核心链路（2-3天）
- [ ] 接入 `pypdf` 或 `unstructured` 做文档解析
- [ ] 接入 `ChromaDB` + `sentence-transformers` 做向量化
- [ ] 写一个完整的 `ingest.py` 流程

### Phase 2: 接入真实LLM（1天）
- [ ] 接入 OpenAI/Claude/通义千问 API
- [ ] 实现真实的HyDE改写

### Phase 3: 端到端验证（1-2天）
- [ ] 准备真实数据集（100篇论文）
- [ ] 跑通完整Pipeline测试
- [ ] 记录真实性能指标

详见 [REALITY_CHECK.md](REALITY_CHECK.md) 中的补全路线图。

---

## 📄 相关文档

| 文档 | 内容 |
|------|------|
| [REALITY_CHECK.md](REALITY_CHECK.md) | 项目真实状态检查（必读） |
| [CONTRIBUTING.md](CONTRIBUTING.md) | 贡献指南 |
| [EXPERIMENTS.md](EXPERIMENTS.md) | 实验记录模板 |

---

## 📊 代码统计

```bash
# 统计代码行数
find src -name "*.py" | xargs wc -l
```

| 模块 | 行数 | 测试覆盖率 |
|------|------|------------|
| 熔断器 | ~400 | 有单元测试 |
| 限流器 | ~200 | 有单元测试 |
| 父子分块 | ~420 | 有单元测试 |
| 评估指标 | ~300 | 有单元测试 |
| 其他模块 | ~1500 | 骨架代码 |

---

## 📄 License

MIT License

---

**本项目是学习性质的实现，诚实是最好的策略。**

如果你发现任何夸大或不实的描述，欢迎提交Issue指正。
