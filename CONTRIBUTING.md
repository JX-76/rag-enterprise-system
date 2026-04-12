# 贡献指南

感谢你对 Enterprise RAG System 的关注！本文档指导你如何参与项目贡献。

---

## 项目定位

这是一个**教学导向**的企业级RAG系统，目标是：
- 展示生产级RAG的完整架构
- 提供可复现的实验数据
- 沉淀可复现、可验证的技术经验

**不是**: 
- 追求SOTA效果的竞赛项目
- 通用的大模型应用框架
- 商业化的闭源产品

---

## 如何贡献

### 1. 代码贡献

**欢迎的贡献**:
- ✅ 修复Bug
- ✅ 补充测试用例
- ✅ 优化文档和注释
- ✅ 添加新的评估指标
- ✅ 改进实验数据生成

**暂不需要**:
- ❌ 新的模型集成（保持简洁）
- ❌ 复杂的UI界面
- ❌ 特定领域的优化（保持通用性）

### 2. 文档贡献

**优先补充**:
- 实验结果的补充和验证
- 常见设计问题与技术取舍说明（Q&A）
- 不同数据源的处理经验
- 性能调优的实践案例

### 3. 实验数据

如果你有真实场景的数据集，欢迎分享：
- 格式：JSON，包含 `question` 和 `answer`
- 领域：垂直领域（医疗、法律、金融等）
- 规模：50+ 问答对

---

## 开发流程

### 环境准备

```bash
# 1. Fork 项目
# 2. Clone 你的Fork
git clone https://github.com/YOUR_NAME/rag-enterprise-system.git

# 3. 创建分支
git checkout -b feature/your-feature

# 4. 安装依赖
pip install -r requirements-dev.txt
```

### 代码规范

**Python代码**:
- 遵循 PEP 8
- 使用类型注解
- 函数必须有 docstring

```python
def calculate_recall(retrieved: List[str], relevant: Set[str]) -> float:
    """
    计算Recall@K
    
    Args:
        retrieved: 检索到的文档ID列表
        relevant: 相关文档ID集合
        
    Returns:
        Recall值，范围[0, 1]
    """
    if not relevant:
        return 0.0
    return len(set(retrieved) & relevant) / len(relevant)
```

**提交信息**:
```
<type>: <subject>

<body>

<footer>
```

Type:
- `feat`: 新功能
- `fix`: 修复Bug
- `docs`: 文档更新
- `test`: 测试相关
- `refactor`: 重构

示例:
```
feat: 添加BM25检索器实现

- 使用rank-bm25库
- 支持中文分词
- 添加单元测试

Closes #123
```

### 提交PR

1. **确保测试通过**:
```bash
pytest tests/ -v
```

2. **更新文档**:
- 修改README（如有新功能）
- 更新EXPERIMENTS.md（如有新实验）

3. **提交PR**:
- PR标题清晰说明改动
- 描述中包含测试方法
- 关联相关Issue

---

## 实验数据规范

如果你贡献实验数据，请遵循：

```json
{
  "experiment": "chunk_size",
  "name": "Chunk Size Impact",
  "description": "测试不同chunk size对检索效果的影响",
  "timestamp": "2024-04-06T14:30:00",
  "data_source": "arxiv_cs_AI",
  "data_size": 100,
  "results": [
    {
      "variant": "small (200)",
      "config": {"size": 200},
      "metrics": {
        "recall@5": 0.65,
        "mrr": 0.45,
        "latency_ms": 35.0
      }
    }
  ]
}
```

---

## 讨论与问题

**GitHub Issues**:
- 🐛 Bug报告
- 💡 功能建议
- ❓ 使用问题
- 📊 实验分享

**Discussions**:
- 技术交流
- 技术实践经验分享
- 行业动态讨论

---

## 贡献者名单

感谢所有贡献者（按字母顺序）：

- [JX-76](https://github.com/JX-76) - 项目创建者

*你的名字可以出现在这里！*

---

## 许可证

本项目采用 [MIT License](LICENSE)。

贡献即表示你同意你的代码将在MIT许可证下发布。

---

**感谢你的贡献！** 🎉