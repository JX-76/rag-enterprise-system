# Commit重构计划

## 当前问题
原有commit是同一天批量提交，需要按开发逻辑拆分。

## 重构后提交历史（按时间顺序）

### Phase 1: 基础设施 (Day 1)
```
feat: 项目初始化 - 添加项目结构和基础配置
- 创建src目录结构
- 添加.gitignore, LICENSE
- 创建基础requirements.txt

feat: 实现熔断器核心模块
- 三态状态机: CLOSED/OPEN/HALF_OPEN
- 自动恢复机制
- 线程安全实现
- 400+行完整代码

feat: 实现限流器核心模块
- Token Bucket算法
- 支持突发流量
- 200+行完整代码

test: 添加熔断器和限流器单元测试
- test_circuit_breaker.py
- test_rate_limit.py
- 全部通过验证
```

### Phase 2: 核心功能 (Day 2-3)
```
feat: 实现父子分块策略
- Parent-Child Chunking算法
- 滑动窗口 + 语义边界
- 420+行完整代码

test: 添加父子分块单元测试
- test_parent_child_chunker.py
- 覆盖分块、关联、上下文完整性

feat: 实现评估指标计算
- Recall@K, MRR, NDCG
- 支持多维度评估
- 300+行完整代码

docs: 添加项目文档和博客
- REALITY_CHECK.md - 诚实声明
- blog/01-circuit-breaker-rate-limit.md
- 面试谈资指南
```

### Phase 3: MVP实现 (Day 4-6) [待完成]
```
feat: 实现文档解析模块 (MVP)
- PDF解析 (pypdf)
- Markdown/TXT支持
- 语义分块策略

feat: 实现向量化与向量存储 (MVP)
- BGE Embedding
- ChromaDB存储
- 支持增量索引

feat: 实现多路混合检索 (MVP)
- Dense + BM25
- RRF融合
- 端到端可运行

feat: 实现查询改写 (MVP)
- Multi-Query扩展
- HyDE框架

feat: 实现LLM生成与引用溯源 (MVP)
- 兼容OpenAI API
- 引用标注
- 幻觉检测框架

docs: 添加端到端Demo和实验数据
- quickstart.py 真实可运行
- EXPERIMENTS.md 实测数据
```

## 执行策略
由于历史commit已推送到GitHub，采用"向前修复"策略：
1. 保留现有commit历史（诚实声明的一部分）
2. 从当前状态继续按Phase 3推进
3. 每个功能完成后独立commit
4. 最终形成清晰的迭代历史

## 当前状态
✅ Phase 1 完成: 熔断器、限流器、测试
✅ Phase 2 完成: 父子分块、评估指标、文档
⏳ Phase 3 进行中: MVP实现
