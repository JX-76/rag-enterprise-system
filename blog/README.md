# RAG技术博客

> 从工程实践出发，深入解析企业级RAG系统的设计与优化

---

## 已发布文章

### [01. 生产环境RAG的熔断与限流：从玩具到企业级](01-circuit-breaker-rate-limit.md)

**关键词**: 熔断器、限流器、故障恢复、高可用

**核心内容**:
- 真实故障案例：Milvus超时导致的级联故障
- 三态熔断器设计（CLOSED/OPEN/HALF_OPEN）
- Token Bucket多级限流策略
- 从故障到恢复的完整链路

**实践亮点**:
> "我们遇到过Milvus磁盘满了导致全系统雪崩，后来加了熔断器，MTTR从25分钟降到30秒。"

---

## 待发布文章

| 序号 | 主题 | 关键词 | 状态 |
|------|------|--------|------|
| 02 | 父子分块策略：解决长文档检索的语义断裂 | Parent-Child Chunking、滑动窗口 | 📝 待写 |
| 03 | 三阶重排序：平衡精度与延迟的工程实践 | Reranking、Latency、BGE | 📝 待写 |
| 04 | 查询改写：HyDE与Multi-Query的选择与权衡 | HyDE、Query Expansion | 📝 待写 |
| 05 | 混合检索：Dense + Sparse + BM25的RRF融合 | Hybrid Retrieval、RRF | 📝 待写 |
| 06 | RAG评估体系：如何科学评估你的系统 | Metrics、Recall、NDCG | 📝 待写 |
| 07 | 多租户架构：数据隔离与资源配额 | Multi-tenancy、RBAC | 📝 待写 |
| 08 | 从0到1构建生产级RAG：完整实战指南 | Best Practices、Deployment | 📝 待写 |

---

## 写作原则

1. **真实案例**: 每个方案都基于实际故障或优化经验
2. **量化数据**: 有指标、有对比、有结论
3. **可复现**: 提供完整代码和测试方法
4. **实践导向**: 每篇文章尽量补充设计取舍、故障经验或可复现结论

---

## 阅读建议

**按顺序阅读**:
1. 先读 [01-circuit-breaker-rate-limit.md](01-circuit-breaker-rate-limit.md) 了解生产级系统的稳定性设计
2. 配合 [EXPERIMENTS.md](../EXPERIMENTS.md) 查看实验数据
3. 结合代码 [src/](../src/) 理解实现细节

**阅读与复盘**:
- 每篇文章的“实践亮点”段落可作为技术复盘切入点
- 配合GitHub代码展示工程能力
- 用EXPERIMENTS.md中的数据支撑你的观点

---

*持续更新中，欢迎Star和关注*