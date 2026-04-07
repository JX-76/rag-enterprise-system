# RAG Enterprise System - API 文档

## 快速开始

```python
from rag.pipeline import DefaultRAGPipeline, RAGConfig

# 创建Pipeline
config = RAGConfig(chunk_size=500, top_k=10)
pipeline = DefaultRAGPipeline(config)

# 文档入库
pipeline.ingest_document("document.pdf")

# 查询
result = pipeline.query("什么是RAG？")
print(result.answer)

# 多轮对话
result = pipeline.chat(
    query="它有什么优势？",
    session_id="session_001",
    user_id="user_001",
    use_memory=True
)
```

## 核心类

### RAGConfig

RAG流水线配置类。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| chunk_size | int | 500 | 文档分块大小 |
| chunk_overlap | int | 50 | 分块重叠大小 |
| embedding_model | str | "BAAI/bge-small-zh-v1.5" | Embedding模型 |
| top_k | int | 10 | 检索Top-K |
| use_hybrid | bool | True | 是否使用混合检索 |

### DefaultRAGPipeline

主要流水线类。

#### 方法

**ingest_document(file_path)**
- 单文档入库
- 返回: `IngestResult`

**ingest_documents(file_paths, show_progress=True)**
- 批量文档入库
- 返回: `List[IngestResult]`

**query(query, use_rewrite=True)**
- 单次查询
- 返回: `QueryResult`

**chat(query, session_id, user_id, use_memory=True)**
- 对话式查询（支持Memory）
- 返回: `QueryResult`

**get_memory_stats(user_id)**
- 获取记忆统计
- 返回: `Dict`

## Memory 四层架构

### 层级说明

| 层级 | 存储 | 用途 | TTL |
|------|------|------|-----|
| 超短期 | 内存 | 当前会话上下文 | 会话期间 |
| 短期 | Redis | 近7天对话历史 | 7天 |
| 长期 | PostgreSQL | 用户画像偏好 | 永久 |
| 全局 | 向量库 | 企业知识库 | 永久 |

### MemoryManager

```python
from memory import MemoryManager

manager = MemoryManager()

# 添加消息到当前会话
manager.add_to_session_context(
    user_id="user_001",
    session_id="session_001",
    role="user",
    content="什么是RAG？"
)

# 获取会话上下文
context = manager.get_session_context("user_001", "session_001")

# 构建完整记忆上下文
full_context = manager.build_memory_context(
    user_id="user_001",
    session_id="session_001",
    query="它有什么优势？"
)
```

## 性能优化

### 向量检索缓存

```python
from utils.performance_optimizer import vector_cache

# 缓存自动启用
# 查看统计
stats = vector_cache.get_stats()
print(f"缓存命中率: {stats['hit_rate']}")
```

### 性能监控

```python
from utils.performance_optimizer import performance_monitor

# 查看性能报告
report = performance_monitor.get_report()
print(report)
```

## 运行测试

```bash
# 集成测试
python scripts/run_integration_tests.py

# 轻量级记忆测试
python test_memory_lightweight.py
```
