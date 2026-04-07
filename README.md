# 基于 LangChain+Milvus 的大模型 RAG 问答实战 Demo（含踩坑复盘）

> **定位**：个人求职实战项目 | 单机版可运行 | 全流程开发记录
> 
> **核心价值**：文档上传→解析→分块→向量化→检索→大模型问答完整闭环，重点记录开发中的技术问题与解决方案

---

## 项目简介

这是一个**个人求职实战项目**，实现了大模型 RAG（检索增强生成）系统的完整流程：

```
文档上传 → 解析分块 → Embedding向量化 → 向量入库 → 用户查询 → 检索相关文档 → 拼接Prompt → 大模型生成回答
```

**非生产级分布式系统**，单机版即可运行，适合：
- 求职面试时演示完整技术能力
- 学习 RAG 全流程开发
- 理解大模型应用的实际落地问题

**技术诚实声明**：本项目为求职 Demo，功能完整但非企业级，已知的局限性会在文档中如实说明。

---

## 技术栈（精简可落地）

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

**删除的冗余技术栈**（为短期落地）：
- ❌ Celery + Redis → 改为 FastAPI 同步任务
- ❌ PostgreSQL → 改为 SQLite
- ❌ Prometheus + Grafana → 改为控制台日志
- ❌ K8s/Helm/Terraform → 改为单机 Docker

---

## 快速开始（3 步跑通）

### 1. 环境准备

```bash
# 克隆项目
git clone https://github.com/JX-76/rag-enterprise-system.git
cd rag-enterprise-system

# 安装依赖
pip install -r requirements.txt
```

### 2. 启动 Milvus（向量数据库）

```bash
# 方式1：Docker 启动（推荐）
docker-compose up -d milvus

# 方式2：本地安装 Milvus Standalone
# 参考：https://milvus.io/docs/install_standalone-docker.md
```

### 3. 启动服务

```bash
# 配置大模型（修改 config.py）
# 支持本地模型或在线 API

# 启动 FastAPI 服务
python main.py

# 访问接口文档
open http://localhost:8000/docs
```

---

## Demo 功能演示

### 1. 上传文档

```bash
curl -X POST "http://localhost:8000/api/v1/documents/upload" \
  -H "accept: application/json" \
  -F "file=@test_document.pdf"
```

**支持的格式**：PDF、DOCX、TXT（带格式校验，拒绝非法格式）

### 2. 问答查询

```bash
curl -X POST "http://localhost:8000/api/v1/chat/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "这份文档的主要内容是什么？",
    "session_id": "test_session"
  }'
```

**返回**：基于检索文档的大模型生成答案

### 3. 查看文档列表

```bash
curl "http://localhost:8000/api/v1/documents/"
```

### 4. 删除文档

```bash
curl -X DELETE "http://localhost:8000/api/v1/documents/{doc_id}"
```

---

## 核心技术实现

### 1. 文档处理模块

**语义分块策略**：
- 按段落、标点拆分，避免语义割裂
- 配置参数：`chunk_size=512`, `chunk_overlap=64`
- 短文档不拆分，长文档保留上下文关联

**异常处理**：
- PDF 扫描件、加密 PDF 捕获异常并返回明确提示
- 中文乱码问题：pdfplumber + UTF-8 编码

### 2. 向量数据库模块

**抽象层设计**：
```python
class VectorDB(ABC):
    @abstractmethod
    def add(self, documents): pass
    
    @abstractmethod
    def search(self, query_embedding, top_k): pass
```

- Milvus 实现类继承基类，后续可快速切换
- 连接池管理，避免重复连接报错

### 3. RAG 检索生成模块

**Hybrid 检索**（向量+关键词）：
- Dense 向量检索：语义匹配
- BM25 关键词检索：精确匹配
- RRF 融合排序：综合两种检索结果

**Prompt 工程**：
```
你是一位专业助手。请仅基于以下检索到的文档内容回答问题。
如果文档中没有相关信息，请明确回答"未找到相关信息"。

检索文档：
{retrieved_documents}

用户问题：{question}

请给出准确、简洁的回答：
```

**幻觉检测基础版**：
- 对比回答与检索文档的相似度
- 匹配度低于 50% 标记为疑似幻觉，返回提示

### 4. 大模型接入

**双模式支持**：
- 本地模型：LM Studio 部署 Qwen-7B/Llama3（4bit 量化）
- 在线 API：通义千问、文心一言（配置文件切换）

**参数可配置**：
- `temperature`、`top_p`、`max_tokens` 控制生成随机性

---

## 开发踩坑与问题解决

详细记录见 [DEVELOP_PIT.md](./DEVELOP_PIT.md)

### 精选踩坑案例

#### 1. PDF 解析中文乱码
- **问题**：pypdf 解析部分 PDF 后中文显示乱码
- **原因**：编码支持不佳，未指定中文编码
- **解决**：pdfplumber 补充解析 + 强制 UTF-8

#### 2. 向量检索精度低
- **问题**：用户查询匹配不到相关文档
- **原因**：固定 token 分块割裂语义，单一向量检索覆盖不全
- **解决**：语义分块 + BM25 混合检索 + RRF 融合

#### 3. 本地大模型显存溢出
- **问题**：7B 模型运行时显存不足崩溃
- **原因**：模型未量化，硬件配置不足
- **解决**：4bit 量化 + 降低上下文长度 + 在线 API 兜底

#### 4. Milvus 容器连接失败
- **问题**：Docker 启动后项目无法连接 Milvus
- **原因**：端口映射错误，容器网络不通
- **解决**：修改 docker-compose 网络配置，添加健康检查

---

## 项目结构

```
rag-enterprise-system/
├── main.py                    # FastAPI 入口
├── config.py                  # 全局配置（模型地址、向量库配置等）
├── requirements.txt           # 依赖列表
├── docker-compose.yml         # Docker 部署配置
├── Dockerfile                 # 项目镜像构建
├── src/
│   ├── document/             # 文档处理模块
│   │   ├── parser.py         # PDF/DOCX/TXT 解析
│   │   └── chunker.py        # 语义分块
│   ├── vector/               # 向量数据库模块
│   │   ├── base.py           # 抽象基类
│   │   └── milvus_store.py   # Milvus 实现
│   ├── llm/                  # 大模型接入
│   │   ├── base.py           # 抽象基类
│   │   ├── local_model.py    # 本地模型
│   │   └── api_model.py      # 在线 API
│   ├── rag/                  # RAG 核心
│   │   ├── retriever.py      # Hybrid 检索
│   │   ├── query_rewriter.py # 查询改写
│   │   └── generator.py      # 生成回答
│   ├── api/                  # 接口服务
│   │   └── routes.py         # FastAPI 路由
│   └── utils/                # 工具函数
├── tests/                    # 测试文件
└── docs/
    ├── DEVELOP_PIT.md        # 踩坑复盘文档
    └── COMMIT_REFACTOR.md    # 项目迭代记录
```

---

## 项目迭代记录

见 [COMMIT_REFACTOR.md](./COMMIT_REFACTOR.md)

- **v1.0 → v2.0**：从玩具 Demo 整改为全流程实战 Demo
- 精简冗余技术栈，聚焦核心 RAG 功能
- 新增踩坑复盘文档，体现问题解决能力

---

## 求职展示建议

### 演示重点

1. **功能闭环**：展示完整的文档上传→问答流程
2. **技术深度**：讲解 Hybrid 检索、Prompt 工程、幻觉检测
3. **问题解决**：重点讲 3-4 个踩坑案例的解决过程
4. **诚实性**：明确说明是 Demo 而非生产级，体现技术诚实

### 话术示例

> "这是一个我独立开发的 RAG Demo，实现了从文档处理到大模型生成的完整流程。
> 过程中遇到了 PDF 乱码、检索精度低、显存溢出等问题，通过语义分块、混合检索、模型量化等方法解决。
> 项目为单机版 Demo，功能完整但非企业级，后续可扩展为分布式系统。"

---

## 已知局限性

1. **单机版**：非分布式，不支持高并发
2. **基础格式**：仅支持 PDF/DOCX/TXT，不支持多模态
3. **简单监控**：仅控制台日志，无专业监控大盘
4. **基础幻觉检测**：仅文本相似度匹配，非深度语义验证

**后续优化方向**：分布式部署、多模态支持、高级幻觉检测

---

## 相关链接

- **项目地址**：https://github.com/JX-76/rag-enterprise-system
- **Milvus 文档**：https://milvus.io/docs
- **LangChain 文档**：https://python.langchain.com

---

> 工具的价值在于使用。运行起来，踩坑复盘，才是你的实战经验。

*Version: v2.0 | 求职实战版 | 2026-04-08*
