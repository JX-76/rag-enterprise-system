# RAG Enterprise System：从零手写企业级检索增强生成系统

> 一个面向工程师的RAG架构学习项目，用生产级代码理解检索增强生成的核心原理

---

## 🛠️ 技术栈

| 层级 | 选型 | 说明 |
|------|------|------|
| **API框架** | FastAPI | 异步高性能，类型安全 |
| **LLM框架** | LangChain | 快速接入多厂商LLM |
| **向量数据库** | ChromaDB → Milvus | 渐进式升级 |
| **Embedding** | BGE | 中文优化，本地部署 |
| **LLM** | OpenAI / 通义千问 | 主备切换 |
| **数据库** | PostgreSQL + Redis | 关系+缓存 |
| **任务队列** | Celery | 异步文档处理 |
| **监控** | Prometheus + Grafana | 性能观测 |
| **部署** | Docker / Kubernetes | 按需选择 |

详见 [docs/tech-stack.md](docs/tech-stack.md)

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
from src.retrieval.hybrid_search import HybridRetriever, create_hybrid_retriever

# 创建混合检索器
retriever = create_hybrid_retriever(
    vector_store=chroma_store,    # Dense检索
    bm25_index_dir="./bm25_index", # BM25检索
    rrf_k=60,
    dense_weight=0.5,
    bm25_weight=0.5
)

# 搜索
results = retriever.search(
    query="什么是深度学习？",
    query_embedding=query_vec,
    top_k=10
)
```

RRF公式：`score = Σ(1 / (k + rank))`，k通常取60。支持可配置权重调整。

代码位置：`src/retrieval/hybrid_search.py`

### 5. 查询改写：提升检索召回率

用户查询往往简短模糊，直接检索可能遗漏相关内容。查询改写通过生成多个查询变体，提升召回率。

支持两种策略：

**Multi-Query**：生成语义相同的多个查询变体
```python
from src.rag.query_rewriter import QueryRewriter

rewriter = QueryRewriter()
rewritten = rewriter.rewrite(
    "什么是机器学习？",
    strategies=['multi_query'],
    num_variations=3
)
# 输出：
# - 什么是机器学习？
# - 机器学习？（去除疑问词）
# - 什么是machine learning？（同义词替换）
```

**HyDE（Hypothetical Document Embeddings）**：生成假设答案再检索
```python
rewritten = rewriter.rewrite(
    "什么是深度学习？",
    strategies=['hyde']
)
# 输出假设文档：
# "关于什么是深度学习，主要内容包括定义、原理、应用场景和实现方法。"
```

代码位置：`src/rag/query_rewriter.py`

### 6. 向量化服务：文本到向量的转换

使用BGE模型将文本转换为向量，支持ChromaDB存储。

```python
from src.services.embedding_service import EmbeddingService, VectorStore

# 创建向量化服务
embedder = EmbeddingService()

# 编码文本
texts = ["机器学习简介", "深度学习原理"]
embeddings = embedder.encode(texts)

# 存储到ChromaDB
store = VectorStore()
store.add_documents(
    documents=[{"id": "1", "text": "...", "metadata": {}}],
    embeddings=embeddings
)

# 搜索
results = store.search(query_embedding, top_k=5)
```

支持批量编码、归一化、查询指令增强（BGE推荐）。

代码位置：`src/services/embedding_service.py`

### 7. LLM生成服务：本地模型与API兼容

支持两种调用方式：

**本地模型**（transformers）：
```python
from src.services.llm_service import LocalLLM

llm = LocalLLM(
    model_name="Qwen/Qwen2-1.5B-Instruct",
    device="cpu"
)
response = llm.generate("你好")
```

**API模型**（OpenAI格式）：
```python
from src.services.llm_service import APILLM

llm = APILLM(
    api_key="sk-...",
    base_url="https://api.openai.com/v1",
    model="gpt-3.5-turbo"
)
response = llm.generate("你好")
```

**RAG生成器**（支持引用溯源）：
```python
from src.services.llm_service import RAGGenerator

generator = RAGGenerator(llm=llm, enable_citation=True)
response = generator.generate(
    query="什么是机器学习？",
    context_docs=retrieved_docs
)
# response.citations 包含引用来源
# response.hallucination_detected 标记幻觉内容
```

代码位置：`src/services/llm_service.py`

### 8. 文档解析：多格式支持

支持PDF、Markdown、Word、纯文本解析。

```python
from src.ingestion.document_parser import DocumentParser

parser = DocumentParser(
    chunk_size=512,      # 目标分块大小
    chunk_overlap=128,   # 重叠保持上下文
    respect_semantic_boundaries=True  # 优先在语义边界切分
)

# 解析单个文件
doc = parser.parse("document.pdf")

# 解析整个目录
docs = parser.parse_directory("./data", recursive=True)
```

语义分块策略：优先在标题、段落边界切分，避免句子中间截断。

代码位置：`src/ingestion/document_parser.py`

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
│   ├── api/middleware/          # 服务保护中间件
│   │   ├── circuit_breaker.py   # 熔断器（400+行，完整实现）
│   │   └── rate_limit.py        # 限流器（200+行，完整实现）
│   ├── ingestion/               # 数据接入层
│   │   ├── document_parser.py   # 文档解析（600+行，多格式支持）
│   │   └── parent_child_chunker.py  # 父子分块（420+行）
│   ├── evaluation/              # 评估层
│   │   └── metrics.py           # 检索指标（300+行，Recall/MRR/NDCG）
│   ├── retrieval/               # 检索层
│   │   └── hybrid_search.py     # 混合检索（350+行，RRF融合）
│   ├── services/                # 服务层
│   │   ├── embedding_service.py # 向量化（400+行，BGE+ChromaDB）
│   │   └── llm_service.py       # LLM服务（500+行，本地+API）
│   └── rag/                     # RAG核心
│       └── query_rewriter.py    # 查询改写（250+行，Multi-Query+HyDE）
├── tests/unit/                  # 单元测试
│   ├── test_circuit_breaker.py  # 熔断器测试
│   ├── test_rate_limit.py       # 限流器测试
│   └── test_parent_child_chunker.py  # 分块测试
├── demo_end_to_end.py           # 端到端演示脚本
├── quickstart.py                # 核心模块快速测试
├── requirements.txt             # 依赖管理
└── README.md                    # 项目说明
```

---

## 学习建议：怎么用这个项目的代码

### 场景一：准备面试

如果你正在准备RAG相关的技术面试，可以重点看这几个文件：

1. `src/api/middleware/circuit_breaker.py` - 熔断器状态机
2. `src/ingestion/parent_child_chunker.py` - 父子分块策略
3. `src/evaluation/metrics.py` - 检索评估指标


### 场景二：学习架构设计

如果你想理解企业级RAG系统的模块划分，可以看：

- 目录结构如何组织
- 模块之间的接口如何定义
- 配置和实现的分离


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

## 模块详细说明

### 服务保护中间件（api/middleware/）

生产环境的核心稳定性保障。

**熔断器**（`circuit_breaker.py`）：
- 三态状态机：CLOSED/OPEN/HALF_OPEN
- 自动故障检测和恢复
- 线程安全实现
- 使用示例见上文

**限流器**（`rate_limit.py`）：
- Token Bucket算法
- 支持突发流量
- 可配置rate和capacity
- 使用示例见上文

### 数据接入层（ingestion/）

**文档解析**（`document_parser.py`）：
- 支持格式：PDF（pypdf）、Word（python-docx）、Markdown、TXT
- 语义分块：优先在标题、段落边界切分
- 滑动窗口：保持上下文连续性
- 多编码支持：UTF-8、GBK、Latin-1自动检测
- 代码行数：600+

**父子分块**（`parent_child_chunker.py`）：
- Parent-Child策略解决检索粒度矛盾
- 子块小精度高，父块大上下文完整
- ID关联机制
- 代码行数：420+

### 检索层（retrieval/）

**混合检索**（`hybrid_search.py`）：
- DenseRetriever：基于ChromaDB的向量检索
- BM25Retriever：基于Whoosh的稀疏检索
- HybridRetriever：RRF融合，可配置权重
- 代码行数：350+

### RAG核心（rag/）

**查询改写**（`query_rewriter.py`）：
- Multi-Query：生成多个查询变体
- HyDE：生成假设答案再检索
- 支持LLM增强（可选）
- 代码行数：250+

### 服务层（services/）

**向量化服务**（`embedding_service.py`）：
- EmbeddingService：BGE模型编码
- VectorStore：ChromaDB封装
- RAGIngestionPipeline：文档入库Pipeline
- 支持批量编码、归一化、查询指令
- 代码行数：400+

**LLM服务**（`llm_service.py`）：
- LocalLLM：transformers本地模型（Qwen等）
- APILLM：OpenAI格式API
- RAGGenerator：支持引用溯源的生成器
- 基础幻觉检测
- 代码行数：500+

### 评估层（evaluation/）

**评估指标**（`metrics.py`）：
- Recall@K：召回率
- Precision@K：精确率
- MRR：平均倒数排名
- MAP：平均精度均值
- NDCG@K：归一化折损累积增益
- 代码行数：300+

---

## 代码统计

```bash
find src -name "*.py" | xargs wc -l
```

| 模块 | 代码行数 | 测试状态 | 依赖要求 |
|------|---------|----------|---------|
| 熔断器 | ~400 | 单元测试通过 | 无 |
| 限流器 | ~200 | 单元测试通过 | 无 |
| 父子分块 | ~420 | 单元测试通过 | 无 |
| 评估指标 | ~300 | 单元测试通过 | 可选numpy |
| 文档解析 | ~600 | 可运行 | pypdf, python-docx（可选） |
| 向量化服务 | ~400 | 可运行 | torch, sentence-transformers, chromadb（可选） |
| 混合检索 | ~350 | 可运行 | whoosh（可选） |
| 查询改写 | ~250 | 可运行 | 无 |
| LLM服务 | ~500 | 可运行 | transformers, openai（可选） |

**总计**：约3400行Python代码

---

## 🚀 快速启动

### 方式一：Docker Compose（推荐）

```bash
# 1. 克隆项目
git clone https://github.com/JX-76/rag-enterprise-system.git
cd rag-enterprise-system

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 填入你的 OpenAI API Key

# 3. 启动服务
docker-compose up -d

# 4. 访问服务
# API: http://localhost:8000
# 文档: http://localhost:8000/docs
# Grafana: http://localhost:3000 (admin/admin)
```

### 方式二：本地运行

```bash
# 1. 安装依赖
pip install -r requirements-full.txt

# 2. 配置环境变量
export OPENAI_API_KEY=sk-your-key

# 3. 启动服务
python -m src.api.main

# 4. 测试
python quickstart.py
```

### 方式三：LangChain集成

```python
from examples.langchain_integration import CustomRAGPipeline

# 创建Pipeline
pipeline = CustomRAGPipeline(
    embedding_model="BAAI/bge-small-zh-v1.5",
    llm_model="gpt-3.5-turbo",
    use_custom_chunker=True  # 使用本项目的父子分块
)

# 接入文档
pipeline.ingest_documents(["你的文档内容"])

# 查询
result = pipeline.query("你的问题")
print(result["answer"])
```

---

## 🔗 与主流框架的关系

本项目**不是**为了替代LangChain/LlamaIndex，而是**补充和深化**。

### 为什么需要自定义实现？

| 场景 | LangChain默认 | 本项目定制 |
|------|--------------|-----------|
| 熔断保护 | ❌ 无内置 | ✅ 三态状态机 |
| 父子分块 | ❌ 无关联ID | ✅ Parent-Child关联 |
| RRF融合 | ✅ 有 | ✅ 更灵活权重控制 |
| 评估指标 | ✅ Ragas | ✅ 手写计算逻辑 |

### 使用方式

**推荐模式**：LangChain快速搭建 + 本项目深度定制

```python
# 1. 用LangChain快速搭建原型
from langchain import OpenAI
from langchain.vectorstores import Chroma

# 2. 用本项目优化核心模块
from src.ingestion.parent_child_chunker import ParentChildChunker
from src.api.middleware.circuit_breaker import CircuitBreaker

# 3. 组合使用
chunker = ParentChildChunker()  # 自定义分块
docs = chunker.chunk(text)
# ... 转换为LangChain Document继续流程
```

详见 [examples/langchain_integration.py](examples/langchain_integration.py)

---

## 📚 API文档

启动服务后访问：
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

主要接口：
- `POST /ingest` - 文档接入
- `POST /query` - 智能查询
- `GET /health` - 健康检查
- `GET /metrics` - Prometheus指标

---

## License

MIT License

---

这个项目是个人学习RAG系统的代码记录。如果代码对你有帮助，欢迎Star。如果发现代码有问题，欢迎提Issue指正。
