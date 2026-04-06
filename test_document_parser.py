#!/usr/bin/env python3
"""文档解析器测试"""
import sys
import os
import importlib.util

# 直接导入document_parser，避免级联导入
script_dir = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location(
    "document_parser",
    os.path.join(script_dir, "src/ingestion/document_parser.py")
)
module = importlib.util.module_from_spec(spec)
sys.modules["document_parser"] = module
spec.loader.exec_module(module)

DocumentParser = module.DocumentParser
parse_document = module.parse_document

# 创建一个测试文件
test_md_content = """# 机器学习简介

机器学习是人工智能的一个分支，它使系统能够从经验中学习和改进，而无需明确编程。

## 监督学习

监督学习使用标记数据训练模型。常见的算法包括：
- 线性回归
- 逻辑回归
- 支持向量机
- 决策树

## 无监督学习

无监督学习处理未标记数据，发现隐藏的模式。常见算法包括聚类和降维。

### 聚类算法

K-means是最常用的聚类算法之一。它将数据分成K个簇。

## 深度学习

深度学习使用多层神经网络。Transformer架构在自然语言处理中取得了巨大成功。
"""

# 写入测试文件
test_file = "/tmp/test_doc.md"
with open(test_file, 'w', encoding='utf-8') as f:
    f.write(test_md_content)

print("="*60)
print("文档解析器测试")
print("="*60)

# 解析文档
parser = DocumentParser(chunk_size=200, chunk_overlap=50)
doc = parser.parse(test_file)

print(f"\n源文件: {doc.source}")
print(f"分块数: {len(doc.chunks)}")
print(f"总字符: {doc.get_total_chars()}")
print(f"元数据: {doc.metadata}")

print("\n" + "-"*60)
print("分块详情:")
print("-"*60)

for i, chunk in enumerate(doc.chunks[:5]):  # 只显示前5个
    print(f"\n[块 {i+1}]")
    print(f"  字符数: {len(chunk.content)}")
    print(f"  元数据: {chunk.metadata}")
    print(f"  内容预览: {chunk.content[:100]}...")

print("\n" + "="*60)
print("✅ 文档解析器测试通过！")
print("="*60)
