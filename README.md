# 基于 LangChain+Milvus 的大模型 RAG 问答系统

> 个人求职项目 | 单机可运行 | 完整 RAG 流程实现

---

## 项目简介

本项目实现大模型 RAG（检索增强生成）系统的完整流程：

```
文档上传 → 解析分块 → Embedding向量化 → 向量入库 → 用户查询 → 检索相关文档 → 拼接Prompt → 大模型生成回答
```

**适用场景**：
- 个人技术能力展示
- RAG 全流程学习实践
- 大模型应用快速原型验证

---

## 技术栈

| 层级 | 选型 | 说明 |
|------|------|------|
| **API 框架** | FastAPI | 轻量接口服务，自带 Swagger 文档 |
| **RAG 框架** | LangChain | 简化接入，避免重复造轮子 |
| **向量数据库** | Milvus Standalone | 轻量单机版，部署简单 |
| **Embedding** | BGE-small | 轻量速度快，单机可跑 |
| **大模型** | 本地 Qwen/Llama3 + 在线 API | 双模式适配不同硬件环境 |
| **文档解析** | pypdf + python-docx | 支持 PDF、Word、TXT 基础格式 |
| **数据存储** | SQLite | 零配置，存储文档元数据 |
| **部署** | Docker + Docker Compose | 单机容器化，一键启动 |

---

## 快速开始

### 1. 环境准备

```bash
# 克隆项目
git clone https://github.com/JX-76/rag-enterprise-system.git
cd rag-enterprise-system

# 安装依赖
pip install -r requirements.txt
```

### 2. 启动 Milvus

```bash
docker-compose up -d milvus
```

### 3. 启动服务

```bash
# 启动 FastAPI 服务
python main.py

# 访问接口文档
open http://localhost:8000/docs
```

---

## 功能演示

### 上传文档

```bash
curl -X POST "http://localhost:8000/api/v1/documents/upload" \
  -F "file=@test_document.pdf"
```

### 问答查询

```bash
curl -X POST "http://localhost:8000/api/v1/chat/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "这份文档的主要内容是什么？",
    "session_id": "test_session"
  }'
```

### 查看文档列表

```bash
curl "http://localhost:8000/api/v1/documents/"
```

---

## 核心实现

### 1. 文档处理

- **语义分块**：按段落、标点拆分，`chunk_size=512`, `chunk_overlap=64`
- **格式支持**：PDF、DOCX、TXT
- **异常处理**：加密/扫描 PDF 捕获异常，中文乱码自动处理

### 2. 向量数据库

- **抽象层设计**：基类抽象，Milvus 实现，可快速切换
- **连接管理**：连接池 + 重试机制

### 3. RAG 检索生成

- **Hybrid 检索**：Dense 向量 + BM25 关键词 + RRF 融合
- **Prompt 工程**：约束模型仅基于检索文档回答
- **幻觉检测**：回答与文档相似度校验（基础版）

### 4. 大模型接入

- **本地模型**：LM Studio 部署（4bit 量化）
- **在线 API**：通义千问、OpenAI 兼容接口

---

## 项目结构

```
rag-enterprise-system/
├── main.py                    # FastAPI 入口
├── config.py                  # 全局配置
├── requirements.txt           # 依赖列表
├── docker-compose.yml         # Docker 部署
├── src/
│   ├── document/             # 文档处理
│   │   ├── parser.py
│   │   └── chunker.py
│   ├── vector/               # 向量数据库
│   │   ├── base.py
│   │   └── milvus_store.py
│   ├── llm/                  # 大模型接入
│   │   ├── base.py
│   │   ├── local_model.py
│   │   └── api_model.py
│   ├── rag/                  # RAG 核心
│   │   ├── retriever.py
│   │   └── generator.py
│   └── api/                  # 接口服务
│       └── routes.py
└── docs/
    └── DEVELOP_PIT.md        # 开发踩坑记录
```

---

## 开发记录

见 [docs/DEVELOP_PIT.md](./docs/DEVELOP_PIT.md) - 记录开发过程中的技术问题与解决方案。

---

## 相关链接

- **项目地址**：https://github.com/JX-76/rag-enterprise-system
- **Milvus 文档**：https://milvus.io/docs
- **LangChain 文档**：https://python.langchain.com

---

*Version: v2.0 | 2026-04-08*
