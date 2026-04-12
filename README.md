# 模块化 RAG 系统

> 面向检索质量优化与工程落地的模块化 RAG 项目
> 
> 核心目标：**优化检索质量**，同时体现 **AI 应用工程化能力**。
>
> 当前更适合公开技术展示的重点是：**主链路清晰、模块边界明确、评测口径可补齐**，而不是提前宣称未经验证的线上效果。

---

## 1. 项目定位

这是一个**可插拔、可扩展的模块化 RAG 系统**，重点不在“堆满企业级 buzzword”，而在于把一条完整的 RAG 主链路做扎实，并围绕检索质量优化和工程落地进行设计。

项目主要解决两个问题：

1. **检索质量问题**：如何通过分块、查询改写、混合检索和重排提高召回与命中质量。
2. **应用落地问题**：如何把 RAG 方案组织成一个可运行、可调参、可观测、可扩展的 AI 应用系统。

适用于以下场景：
- 需要构建可解释、可扩展 RAG 主链路的应用系统
- 需要围绕 chunking / rewrite / retrieval / rerank 做检索优化实验
- 需要以 API 形式交付和评估 RAG 能力的工程场景

---

## 2. 核心亮点

### 2.1 检索质量优化
- **Parent-Child Chunking**：小块检索 + 大块生成，兼顾召回精度与上下文完整性。
- **Hybrid Retrieval**：结合 Dense / Sparse / BM25 多路检索，提升复杂查询覆盖率。
- **Query Rewriting**：支持 HyDE、Query Expansion、Multi-Query 等策略，提高召回鲁棒性。
- **Three-Stage Reranking**：分阶段过滤候选结果，在效果和延迟之间做平衡。

### 2.2 模块化工程设计
- API、检索、重排、生成、评估模块解耦。
- 检索链路可插拔，便于替换不同向量库、Embedding 模型和 Reranker。
- 支持本地模型与 OpenAI 兼容 API 双模式接入。

### 2.3 应用工程化能力
- FastAPI 服务化封装。
- 基础中间件能力：限流、熔断、请求级追踪。
- 基础监控与评估接口，便于后续做 benchmark 和效果对比。

### 2.4 Fine-tuning Workflow
- 提供面向检索侧优化的轻量微调轨道，优先支持 **Query Rewrite LoRA / QLoRA**。
- 提供微调数据规划、训练脚手架与评测模板，便于在保持主链路稳定的前提下做增量优化。
- 强调 **baseline vs FT variant** 的对照评估，避免把未验证的训练收益写成既定结论。

---

## 3. 项目主链路

本项目当前主打并建议演示的主链路如下：

```text
Document Ingestion
  -> Chunking
  -> Embedding / Indexing
  -> Query Rewrite
  -> Hybrid Retrieval
  -> Reranking
  -> Context Construction
  -> LLM Generation
  -> Response with Sources
```

对应能力说明：
- **摄取阶段**：文档解析、切块、索引构建。
- **检索阶段**：改写 query、并行检索、多路结果融合。
- **排序阶段**：对候选文档进行精排与压缩。
- **生成阶段**：基于检索结果构造上下文并生成答案。
- **服务阶段**：通过 API、日志、指标将能力暴露为应用系统。

---

## 4. 功能成熟度说明

为了避免“什么都做了但深度不足”的问题，项目中的能力按成熟度分为三层。

### 4.1 Core Implemented（核心已实现）
这些是当前项目的重点能力：

- 文档解析与基础摄取流程
- Parent-Child Chunking
- Hybrid Retrieval
- Query Rewriting（基础策略）
- Three-Stage Reranking
- FastAPI 查询与检索接口
- 基础中间件：限流、熔断、请求追踪
- 基础监控与评估模块

### 4.2 Experimental / Optional（实验性 / 可选模块）
这些模块用于探索扩展方向，不建议作为项目首页主卖点：

- Multi-Query / Session-Aware Rewrite 的更多策略
- Agentic RAG 相关尝试
- Hot Reload
- AB Testing
- Memory / Workflow 等扩展能力

> 当前仓库中以下目录**保留但默认降权**，主要用于实验、扩展或历史探索，不属于建议默认展示的主链路：
> `src/tenancy/`、`src/ab_testing/`、`src/hot_reload/`、`src/agent/`、`src/memory/`、`src/workflow/`、`src/security/rbac.py`
>
> 如果需要解释这些内容，建议表述为：
> **“仓库中保留了部分扩展性尝试，但当前主打与可 defend 的核心仍是 chunking / rewrite / hybrid retrieval / rerank / API 工程化。”**

### 4.3 Planned / Future Work（规划中）
这些能力更适合作为后续演进方向，而不是当前声称“已成熟落地”的内容：

- 更完整的多租户隔离机制
- 完整鉴权 / 权限体系
- 更完善的线上评估与自动回归机制
- 更规范的生产部署模板

---

## 5. 技术栈

| 层级 | 技术选型 | 说明 |
|------|----------|------|
| API 框架 | FastAPI | 提供检索与问答服务接口 |
| 模型接入 | 本地模型 / OpenAI 兼容 API | 兼容不同开发环境 |
| Embedding | Sentence Transformers / BGE 系列 | 支撑语义检索 |
| 检索策略 | Dense + Sparse + BM25 | 混合检索 |
| 重排策略 | 多阶段 Reranker | 提升候选文档质量 |
| 向量存储 | Milvus / FAISS（模块化支持） | 支持不同部署模式 |
| 缓存 / 中间件 | Redis / 自定义中间件 | 限流、熔断、缓存 |
| 监控评估 | Prometheus / 自定义评估模块 | 基础指标与效果评估 |

---

## 6. 为什么不是“Naive RAG”

相比“上传文档 -> 向量检索 -> 直接拼 Prompt”的基础做法，这个项目重点优化了以下几个方面：

### 6.1 Chunking
- 不直接使用固定窗口切块。
- 使用 Parent-Child 结构，减少上下文割裂问题。

### 6.2 Retrieval
- 不依赖单一路径检索。
- 结合 Dense / Sparse / BM25，提高不同查询类型的覆盖能力。

### 6.3 Rewrite
- 不直接把原始 query 丢进检索器。
- 对复杂、模糊或信息不足的 query 先改写，再检索。

### 6.4 Rerank
- 不把初始召回结果直接送入生成。
- 通过多阶段重排压缩候选结果，提高生成上下文质量。

这几个点共同构成了该项目的主要“算法增强”价值。

---

## 7. 项目结构（当前推荐理解方式）

> 注：仓库中仍保留部分实验性目录和历史结构，后续会继续收束。
> 当前建议按以下主干理解项目。
> 更详细的 canonical / legacy 说明见：`docs/STRUCTURE_GUIDE.md`

```text
rag-enterprise-system/
├── src/
│   ├── api/                 # API 路由与中间件
│   ├── core/                # 主引擎、配置、日志、监控
│   ├── ingestion/           # 文档解析、分块、摄取流程
│   ├── retrieval/           # query rewrite / hybrid retrieval
│   ├── rerank/              # 重排模块
│   ├── generation/          # LLM 生成
│   ├── evaluation/          # 评估与指标
│   ├── services/            # 模型与 embedding 服务封装
│   └── utils/               # 缓存、连接池等通用工具
├── tests/                   # 单元测试 / 集成测试 / benchmark
├── docs/                    # 文档与开发说明
├── docker-compose.yml       # 本地依赖启动
└── README.md
```

### 当前不建议作为主线理解的历史目录
- `src/document/` → 建议统一按 `src/ingestion/` 理解
- `src/vector/` → 建议统一按 `src/vector_store/` / 存储层理解
- `src/rag/` → 更适合作为历史聚合层或 orchestration 过渡层理解
- `src/api/main.py` → 历史入口，官方入口已统一到 `src.main:app`

---

## 8. 当前建议演示方式

如果你要演示这个项目，建议不要“把所有模块都讲一遍”，而是沿着一条链路讲清楚：

### Demo 主线
1. 上传或准备文档
2. 进行切块与索引
3. 发起查询
4. 展示 query rewrite 结果
5. 展示 hybrid retrieval 结果
6. 展示 rerank 后的候选变化
7. 展示最终回答和引用来源

### 推荐关注点
- 为什么选择 Hybrid Retrieval
- 为什么需要 Query Rewrite
- Parent-Child Chunking 解决了什么问题
- Reranking 如何在效果和延迟间取舍
- 项目如何从一个算法链路包装成 API 化应用系统

---

## 9. 快速开始

### 9.1 安装依赖

```bash
git clone https://github.com/JX-76/rag-enterprise-system.git
cd rag-enterprise-system
pip install -r requirements.txt
```

### 9.2 启动依赖服务（如 Milvus / Redis）

```bash
docker-compose up -d
```

### 9.3 启动服务

```bash
# 官方 API 入口
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# 或使用兼容启动器
python main.py
```

### 9.4 运行演示脚本

```bash
python examples/demo_quickstart.py
python examples/demo_end_to_end.py
```

### 9.5 查看接口文档

```text
http://localhost:8000/docs
```

---

## 10. 后续改造方向

当前仓库后续会优先沿以下方向继续整理：

1. 收束重复目录和重复入口。
2. 把“核心实现 / 实验模块 / 未来规划”进一步拆清。
3. 增强评估、benchmark 和 bad case 分析的可解释性。
4. 让项目更贴近 AI 应用开发 + 检索优化的公开技术叙事。

---

## 11. 结论

这个项目不追求“展示所有企业级能力”，而是强调：

- **一条完整且可解释的 RAG 主链路**
- **检索质量优化的算法思路**
- **能够落到 API 和工程结构上的应用开发能力**

如果你希望项目同时体现 AI 应用开发与检索优化能力，这个方向会比“泛企业级大而全系统”更聚焦、更可信。
