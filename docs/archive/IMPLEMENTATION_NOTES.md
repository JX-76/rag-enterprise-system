# 实现说明

## 第二阶段更新 (按豆包建议)

### 1. 端到端Pipeline封装 ✅

**新增**: `src/rag/pipeline.py` - DefaultRAGPipeline

```python
pipeline = DefaultRAGPipeline()
pipeline.ingest_documents(["doc.pdf"])  # 解析→分块→向量化→存储
result = pipeline.query("问题")          # 改写→检索→生成
```

**特性**:
- 延迟初始化，按需加载各模块
- 统一配置 RAGConfig
- 批量入库 + 进度显示
- 支持对话模式（接入Memory）

### 2. 轻量级向量存储 ✅

**新增**: `src/retrieval/simple_vector_store.py`

- 纯Python实现，零额外依赖
- 基于余弦相似度的向量检索
- 支持持久化到磁盘
- 自动内容去重
- 生产环境可无缝升级到ChromaDB/Milvus

### 3. Memory四层架构接入 ✅

**Pipeline.chat()** 方法已实现：

```python
result = pipeline.chat(
    query="问题",
    session_id="session_001",  # 会话追踪
    user_id="user_001",        # 用户识别
    use_memory=True            # 启用记忆
)
```

**接入的记忆层级**:
- **超短期**: 当前会话上下文（内存）
- **短期**: 近7天历史对话（Redis）

**实现逻辑**:
1. 检索历史相关对话
2. 融入查询上下文
3. 生成带上下文的回答
4. 保存当前轮次到记忆

### 4. 引用溯源 ✅

Pipeline自动提取引用：
```python
result.citations = [
    {"id": 1, "source": "doc.pdf", "content": "...", "score": 0.95},
    ...
]
```

### 5. 定位校准 ✅

**README更新**:
- 标题: 《轻量级RAG脚手架》
- 定位: 学习型项目 → 轻量脚手架 → 生产系统（渐进式）
- 快速开始: 3行命令跑通

---

## 技术栈

| 组件 | 选型 | 说明 |
|------|------|------|
| 向量存储 | SimpleVectorStore | 轻量级，零依赖 |
| 检索 | 余弦相似度 | 基础实现，可升级 |
| 记忆 | Memory四层 | 已接入超短期+短期 |
| LLM | Qwen/兼容API | 本地+云端双模式 |

---

## 待完成 (第三阶段)

- [ ] Query-Planning升级（意图分类、纠错）
- [ ] 检索反馈闭环（相似度阈值触发二次改写）
- [ ] 增量更新与文档去重优化
- [ ] Milvus向量库适配
- [ ] 集成测试覆盖
