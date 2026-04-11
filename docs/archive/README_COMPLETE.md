# RAG Enterprise System

> 企业级检索增强生成系统 - 生产就绪

## 📋 项目概述

本项目是一个完整的企业级RAG系统，包含以下核心特性：

### 核心功能模块

| 模块 | 功能 | 文件位置 |
|------|------|----------|
| **熔断器** | 防止级联故障 | `src/api/middleware/circuit_breaker.py` |
| **限流器** | Token Bucket算法 | `src/api/middleware/rate_limit.py` |
| **父子分块** | 小块检索+大块生成 | `src/ingestion/parent_child_chunker.py` |
| **三阶重排** | 预排→精排→优化 | `src/rerank/three_stage.py` |
| **查询改写** | HyDE/分解/扩展 | `src/retrieval/rewrite/` |
| **混合检索** | Dense+Sparse+BM25 | `src/retrieval/hybrid.py` |
| **多租户** | 数据隔离 | `src/tenancy/` |
| **AB测试** | 实验管理 | `src/ab_testing/` |
| **热重载** | 模型热更新 | `src/hot_reload/` |

---

## 🚀 快速开始

### 方式1：最快验证（无需依赖）

```bash
# 进入项目目录
cd rag-enterprise-system

# 运行快速演示（无需安装依赖）
python quickstart.py
```

**预期输出：**
```
======================================================================
  RAG Enterprise System - Quick Start Demo
======================================================================

============================================================
  1. 熔断器状态机演示
============================================================
  初始状态: closed
  配置: 失败阈值=3, 恢复超时=5.0s
  ...
✅ 熔断器工作正常！
```

### 方式2：完整部署

```bash
# 1. 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 2. 安装依赖
pip install -r requirements.txt

# 3. 复制环境配置
cp .env.example .env

# 4. 运行测试
python test_all.py

# 5. 启动服务
make run
# 或: uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

**访问：**
- API文档: http://localhost:8000/docs
- 健康检查: http://localhost:8000/api/v1/health
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000

---

## 📁 项目结构详解

```
rag-enterprise-system/
├── src/                          # 源代码
│   ├── api/                      # API层
│   │   ├── middleware/           # 中间件
│   │   │   ├── circuit_breaker.py    # 熔断器
│   │   │   ├── rate_limit.py         # 限流器
│   │   │   └── tracing.py            # 链路追踪
│   │   └── routes/               # 路由
│   │       ├── health.py         # 健康检查
│   │       ├── query.py          # 查询接口
│   │       └── retrieval.py      # 检索接口
│   ├── core/                     # 核心模块
│   │   ├── rag_engine.py         # RAG引擎
│   │   ├── agentic_rag.py        # Agentic RAG
│   │   ├── config.py             # 配置管理
│   │   ├── logging.py            # 日志系统
│   │   └── monitoring.py         # 监控指标
│   ├── retrieval/                # 检索模块
│   │   ├── hybrid.py             # 混合检索
│   │   ├── dense/                # 稠密检索
│   │   ├── sparse/               # 稀疏检索
│   │   └── rewrite/              # 查询改写
│   │       ├── hyde.py           # HyDE改写
│   │       ├── decomposition.py  # 查询分解
│   │       ├── expansion.py      # 查询扩展
│   │       ├── multi_query.py    # 多查询生成
│   │       └── session_aware.py  # 会话感知
│   ├── rerank/                   # 重排序模块
│   │   ├── three_stage.py        # 三阶重排
│   │   └── rankify_adapter.py    # Rankify适配
│   ├── ingestion/                # 数据摄取
│   │   ├── pipeline.py           # 摄取管道
│   │   ├── parent_child_chunker.py # 父子分块
│   │   └── incremental.py        # 增量更新
│   ├── generation/               # 生成模块
│   │   ├── generator.py          # 生成器
│   │   └── llmlingua_compressor.py # 上下文压缩
│   ├── services/                 # 服务层
│   │   ├── embedding_service.py  # Embedding服务
│   │   └── llm_service.py        # LLM服务
│   ├── vector_store/             # 向量存储
│   │   ├── faiss_store.py        # Faiss实现
│   │   └── dual_index.py         # 双索引
│   ├── tenancy/                  # 多租户
│   │   ├── manager.py            # 租户管理
│   │   └── middleware.py         # 租户中间件
│   ├── ab_testing/               # AB测试
│   │   ├── manager.py            # 实验管理
│   │   └── middleware.py         # AB中间件
│   ├── security/                 # 安全模块
│   │   ├── input_validator.py    # 输入验证
│   │   ├── content_filter.py     # 内容过滤
│   │   ├── rbac.py               # 权限控制
│   │   └── audit.py              # 审计日志
│   ├── hot_reload/               # 热重载
│   │   ├── model_manager.py      # 模型管理
│   │   └── watcher.py            # 文件监控
│   ├── evaluation/               # 评估模块
│   │   └── metrics.py            # 评估指标
│   └── utils/                    # 工具函数
│       ├── cache.py              # 缓存工具
│       └── connection_pool.py    # 连接池
├── tests/                        # 测试
│   ├── unit/                     # 单元测试
│   ├── integration/              # 集成测试
│   └── benchmark/                # 性能测试
├── config/                       # 配置文件
├── deploy/                       # 部署配置
│   ├── docker/                   # Docker配置
│   ├── k8s/                      # Kubernetes配置
│   └── monitoring/               # 监控配置
├── examples/                     # 示例代码
│   └── integrated_rag_demo.py    # 集成演示
├── scripts/                      # 脚本
│   └── setup.sh                  # 安装脚本
├── docs/                         # 文档
├── data/                         # 数据目录
├── logs/                         # 日志目录
├── requirements.txt              # 依赖
├── requirements-dev.txt          # 开发依赖
├── docker-compose.yml            # Docker编排
├── Makefile                      # 命令快捷方式
├── pyproject.toml                # 项目配置
├── test_all.py                   # 测试脚本
├── quickstart.py                 # 快速演示
├── README.md                     # 本文件
├── ARCHITECTURE.md               # 架构文档
└── USE_CASES.md                  # 使用案例
```

---

## 🔧 核心模块详解

### 1. 熔断器 (Circuit Breaker)

**文件**: `src/api/middleware/circuit_breaker.py`

**功能**: 防止级联故障，当服务故障率超过阈值时自动熔断

**三种状态**:
- `CLOSED`: 正常，请求通过
- `OPEN`: 熔断，请求快速失败
- `HALF_OPEN`: 半开，试探性放行

**使用示例**:
```python
from src.api.middleware.circuit_breaker import CircuitBreaker, CircuitBreakerConfig

config = CircuitBreakerConfig(
    failure_threshold=3,      # 3次失败触发熔断
    recovery_timeout=30.0,    # 30秒后尝试恢复
    success_threshold=2       # 2次成功恢复
)
breaker = CircuitBreaker("vector_db", config)

# 使用
result = await breaker.call(async_function)
```

### 2. 限流器 (Rate Limiter)

**文件**: `src/api/middleware/rate_limit.py`

**功能**: 基于Token Bucket算法限制请求速率

**使用示例**:
```python
from src.api.middleware.rate_limit import TokenBucket

# 10 token/秒, 容量20
bucket = TokenBucket(rate=10, capacity=20, key="api_user_123")

if await bucket.acquire():
    # 处理请求
    pass
else:
    # 触发限流
    raise HTTPException(429, "Rate limit exceeded")
```

### 3. 父子分块 (Parent-Child Chunker)

**文件**: `src/ingestion/parent_child_chunker.py`

**功能**: 小块用于精确检索，大块用于完整上下文

**原理**:
- **子块(Child)**: 200 tokens，用于向量检索
- **父块(Parent)**: 1000 tokens，用于LLM生成

**使用示例**:
```python
from src.ingestion.parent_child_chunker import ParentChildChunker

chunker = ParentChildChunker(
    parent_size=1000,
    child_size=200,
    overlap=50
)

chunks = chunker.chunk(document_text)
```

### 4. 三阶重排 (Three-Stage Reranking)

**文件**: `src/rerank/three_stage.py`

**流程**:
1. **Stage 1**: 轻量模型快速筛选 (Top 100 → Top 30)
2. **Stage 2**: 重模型精排 (Top 30 → Top 10)
3. **Stage 3**: 位置优化 (Top 10 → Top 5)

### 5. 查询改写 (Query Rewriting)

**文件**: `src/retrieval/rewrite/`

**支持的改写策略**:
- **HyDE**: 生成假设文档
- **Decomposition**: 复杂查询分解
- **Expansion**: 查询扩展
- **Multi-Query**: 多角度查询生成

---

## 🐳 Docker部署

```bash
# 启动所有服务
docker-compose up -d

# 查看状态
docker-compose ps

# 查看日志
docker-compose logs -f api

# 停止服务
docker-compose down
```

**服务组成**:
- `api`: RAG API服务
- `redis`: 缓存和限流
- `milvus`: 向量数据库
- `prometheus`: 指标收集
- `grafana`: 可视化监控

---

## 📊 监控指标

### 系统指标
- `rag_requests_total`: 请求总数
- `rag_latency_seconds`: 请求延迟
- `rag_retrieval_latency`: 检索延迟
- `rag_rerank_latency`: 重排延迟

### 业务指标
- `rag_recall_at_k`: 检索召回率
- `rag_precision_at_k`: 检索精确率
- `rag_faithfulness`: 答案忠实度

---

## 🧪 测试

```bash
# 运行所有测试
make test

# 单元测试
make test-unit

# 集成测试
make test-integration

# 性能测试
make test-benchmark
```

---

## 📝 API文档

### 查询接口

```bash
POST /api/v1/query
Content-Type: application/json

{
    "query": "什么是机器学习?",
    "top_k": 5,
    "rerank": true,
    "compress": true
}
```

**响应**:
```json
{
    "query": "什么是机器学习?",
    "results": [
        {
            "id": "doc_1",
            "content": "机器学习是...",
            "score": 0.95,
            "source": "dense"
        }
    ],
    "metadata": {
        "latency_ms": 120,
        "recall": 0.88
    }
}
```

---

## 🎯 生产部署检查清单

- [ ] 修改 `.env` 中的密钥
- [ ] 配置外部向量数据库 (Milvus/Chroma)
- [ ] 配置外部缓存 (Redis)
- [ ] 配置LLM API密钥
- [ ] 设置日志级别为 INFO/ERROR
- [ ] 启用Prometheus监控
- [ ] 配置Grafana仪表板
- [ ] 设置告警规则

---

## 📚 相关文档

- [ARCHITECTURE.md](ARCHITECTURE.md) - 详细架构设计
- [USE_CASES.md](USE_CASES.md) - 使用案例
- [API文档](http://localhost:8000/docs) - 自动生成

---

## 🤝 贡献

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送分支 (`git push origin feature/AmazingFeature`)
5. 创建 Pull Request

---

## 📄 License

MIT License
