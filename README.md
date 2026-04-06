# RAG Enterprise System：从零手写企业级检索增强生成系统

> 一个面向工程师的RAG架构学习项目，用生产级代码理解检索增强生成的核心原理

---

## 项目背景：为什么做这个项目

检索增强生成（RAG）是目前大模型应用落地的主流技术路线。但市面上大多数教程停留在调用LangChain的层面，对于想要深入理解底层原理的工程师来说，缺乏一个可以逐行研读的生产级代码实现。

这个项目的目标是：**用最接近生产环境的代码，手写RAG系统的核心模块**。不是为了造轮子，而是为了理解轮子是怎么转的。

### 项目定位说明

这是一个**学习性质**的开源项目，目前状态如下：

**已实现并测试通过（可直接运行）**：
- 熔断器（Circuit Breaker）：三态状态机完整实现
- 限流器（Rate Limiter）：Token Bucket算法
- 父子分块（Parent-Child Chunking）：语义分块策略
- 评估指标（Evaluation Metrics）：Recall@K、MRR、NDCG等

**已实现但未接入真实数据（有完整代码结构）**：
- 文档解析（PDF/Markdown/Word/Text）
- 向量化服务（BGE模型 + ChromaDB）
- 混合检索（Dense + BM25 + RRF融合）
- 查询改写（Multi-Query + HyDE）
- LLM生成服务（本地Qwen + API兼容）

**尚未实现**：
- 完整的端到端Pipeline（需要用户自行组装）
- 大规模数据集评测

---

## 技术亮点：值得仔细读的代码

### 1. 熔断器：微服务稳定性设计

生产环境中的向量数据库、LLM服务都可能故障。熔断器的设计参考了Netflix的Hystrix，实现了完整的三态状态机：

```python
from src.api.middleware.circuit_breaker import (
    CircuitBreaker, CircuitBreakerConfig
)

config = CircuitBreakerConfig(
    failure_threshold=3,      # 连续3次失败触发熔断
    recovery_timeout=30.0,    # 30秒后尝试恢复
    success_threshold=2       # 连续2次成功则关闭熔断
)
breaker = CircuitBreaker("vector_db", config)
```

状态转换逻辑：`CLOSED → OPEN → HALF_OPEN → CLOSED`

核心代码在 `src/api/middleware/circuit_breaker.py`，约400行，包含完整的HALF_OPEN探测和恢复机制。

### 2. 父子分块：解决检索粒度的矛盾

RAG的一个经典难题：分块太大会降低检索精度，分块太小会丢失上下文。

父子分块策略的思路是：
- **子块**：小粒度（如200 tokens），用于精准匹配查询
- **父块**：大粒度（如1000 tokens），用于提供完整上下文

检索时匹配子块，返回对应的父块给LLM。

```python
from src.ingestion.parent_child_chunker import ParentChildChunker

chunker = ParentChildChunker(
    parent_size=1000,
    child_size=200,
    child_overlap=40   # 20%重叠保持连续性
)

parent_chunks = chunker.chunk(text)
# 每个parent_chunk包含多个child_chunk
# 子块与父块通过ID关联
```

实现细节包括语义边界识别（优先在标题、段落处切分）和滑动窗口重叠。

### 3. Token Bucket限流：API保护机制

大模型API通常有调用限制。Token Bucket算法既可以限制平均速率，又允许一定突发流量。

```python
from src.api.middleware.rate_limit import TokenBucket

bucket = TokenBucket(rate=10, capacity=20)  # 10/s，桶容量20

if await bucket.acquire():
    # 处理请求
else:
    # 限流拒绝，返回429
```

### 4. 混合检索：多路召回融合

单一检索策略各有优劣：
- Dense向量检索：语义匹配好，但可能漏掉关键词
- BM25：关键词匹配准确，但缺乏语义理解

混合检索同时执行多路召回，用RRF（Reciprocal Rank Fusion）算法融合结果。

```python
# RRF公式：score = Σ(1 / (k + rank))
# k通常取60
```

代码实现支持可配置的权重调整。

---

## 快速上手

### 环境准备

```bash
# Python 3.9+
git clone https://github.com/JX-76/rag-enterprise-system.git
cd rag-enterprise-system

# 基础依赖（运行核心模块测试）
pip install pytest pytest-asyncio

# 完整依赖（运行端到端RAG）
pip install torch transformers sentence-transformers chromadb whoosh pypdf python-docx
```

### 运行测试

```bash
# 熔断器测试
python -m pytest tests/unit/test_circuit_breaker.py -v

# 限流器测试
python -m pytest tests/unit/test_rate_limit.py -v

# 父子分块测试
python -m pytest tests/unit/test_parent_child_chunker.py -v

# 一键运行所有测试
python quickstart.py
```

### 运行端到端演示

```bash
python demo_end_to_end.py
```

这个脚本演示完整的RAG流程：文档解析、分块、查询改写、服务保护机制。

---

## 项目结构

```
rag-enterprise-system/
├── src/
│   ├── api/middleware/          # 熔断器、限流器
│   ├── ingestion/               # 文档解析、父子分块
│   ├── evaluation/              # 评估指标
│   ├── retrieval/               # 混合检索
│   ├── services/                # LLM服务、向量化
│   └── rag/                     # 查询改写
├── tests/unit/                  # 单元测试
├── blog/                        # 技术文章
├── README.md                    # 本文件
└── REALITY_CHECK.md             # 项目状态说明
```

---

## 学习建议：怎么用这个项目的代码

### 场景一：准备面试

如果你正在准备RAG相关的技术面试，可以重点看这几个文件：

1. `src/api/middleware/circuit_breaker.py` - 熔断器状态机
2. `src/ingestion/parent_child_chunker.py` - 父子分块策略
3. `src/evaluation/metrics.py` - 检索评估指标

面试时可以这样介绍：

> "为了深入理解RAG系统，我独立实现了几个核心生产级模块。比如熔断器，实现了三态状态机和自动恢复逻辑；父子分块策略，用小粒度匹配、大粒度提供上下文；还有评估指标的计算逻辑。代码都在GitHub上，有完整单元测试。"

### 场景二：学习架构设计

如果你想理解企业级RAG系统的模块划分，可以看：

- 目录结构如何组织
- 模块之间的接口如何定义
- 配置和实现的分离

### 场景三：动手扩展

如果你想基于这个项目继续开发：

1. **接入真实LLM**：修改 `src/services/llm_service.py`，配置API Key或加载本地模型
2. **接入真实数据**：运行 `pip install pypdf chromadb`，然后用自己的文档测试
3. **跑评测**：准备问答对，用 `src/evaluation/metrics.py` 计算指标

---

## 技术博客

项目配套的技术文章：

- [熔断器与限流器：大模型服务的稳定性设计](blog/01-circuit-breaker-rate-limit.md)

文章特点：基于真实代码讲解，包含面试可谈的技术细节。

---

## 相关文档

| 文档 | 说明 |
|------|------|
| [REALITY_CHECK.md](REALITY_CHECK.md) | 项目真实状态检查，说明哪些模块是完整实现，哪些是骨架代码 |
| [EXPERIMENTS.md](EXPERIMENTS.md) | 实验记录模板 |

---

## 代码统计

```bash
find src -name "*.py" | xargs wc -l
```

| 模块 | 代码行数 | 测试覆盖 |
|------|---------|----------|
| 熔断器 | ~400 | 单元测试通过 |
| 限流器 | ~200 | 单元测试通过 |
| 父子分块 | ~420 | 单元测试通过 |
| 评估指标 | ~300 | 单元测试通过 |
| 文档解析 | ~600 | 可运行 |
| 向量化服务 | ~400 | 可运行 |
| 混合检索 | ~350 | 可运行 |
| 查询改写 | ~250 | 可运行 |
| LLM服务 | ~500 | 可运行 |

---

## License

MIT License

---

这个项目是个人学习RAG系统的代码记录。如果代码对你有帮助，欢迎Star。如果发现代码有问题，欢迎提Issue指正。
