#!/usr/bin/env python3
"""
RAG快速开始 - 一键演示

3行命令跑通完整RAG流程：
    git clone https://github.com/JX-76/rag-enterprise-system.git
    cd rag-enterprise-system && pip install -r requirements-mvp.txt
    python examples/demo_quickstart.py

定位：轻量级RAG脚手架，开箱即用
"""
import os
import sys
import tempfile
from pathlib import Path

# 确保能找到src模块
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.rag.pipeline import DefaultRAGPipeline, RAGConfig


def create_sample_document():
    """创建示例文档"""
    sample_text = """# RAG技术简介

## 什么是RAG

检索增强生成（Retrieval-Augmented Generation, RAG）是一种将检索技术与生成模型结合的方法。
它通过从外部知识库中检索相关信息，并将其作为上下文提供给语言模型，从而生成更准确、更可靠的回答。

## RAG的核心优势

1. **减少幻觉**：通过引用真实文档，降低模型编造信息的概率
2. **知识更新**：无需重新训练模型，只需更新知识库即可注入新知识
3. **可解释性**：回答可追溯到具体的文档来源
4. **成本效益**：相比微调大模型，RAG的实施成本更低

## RAG的工作流程

1. 文档处理：解析、分块、向量化
2. 检索：根据查询找到相关文档片段
3. 生成：结合检索结果生成回答

## 应用场景

- 企业知识库问答
- 智能客服
- 文档摘要与分析
- 代码辅助生成

## 技术挑战

- 检索准确性
- 上下文长度限制
- 多文档融合
- 实时性要求
"""
    
    # 创建临时文件
    with tempfile.NamedTemporaryFile(
        mode='w', suffix='.md', delete=False, encoding='utf-8'
    ) as f:
        f.write(sample_text)
        return f.name


def demo_ingest():
    """演示：文档入库"""
    print("=" * 60)
    print("步骤1: 文档入库")
    print("=" * 60)
    
    # 创建示例文档
    doc_path = create_sample_document()
    print(f"创建示例文档: {doc_path}")
    
    # 初始化Pipeline
    config = RAGConfig(
        chunk_size=300,
        chunk_overlap=50,
        top_k=5
    )
    pipeline = DefaultRAGPipeline(config)
    
    # 文档入库
    result = pipeline.ingest_document(doc_path)
    
    if result.success:
        print(f"✓ 入库成功")
        print(f"  文件: {result.file_path}")
        print(f"  分块数: {result.chunks_count}")
    else:
        print(f"✗ 入库失败: {result.error}")
    
    # 清理临时文件
    os.unlink(doc_path)
    
    return pipeline


def demo_query(pipeline: DefaultRAGPipeline):
    """演示：问答查询"""
    print("\n" + "=" * 60)
    print("步骤2: 问答查询")
    print("=" * 60)
    
    test_queries = [
        "什么是RAG？",
        "RAG有什么优势？",
        "RAG的工作流程是什么？",
    ]
    
    for idx, query in enumerate(test_queries, 1):
        print(f"\n查询 {idx}: {query}")
        print("-" * 40)
        
        result = pipeline.query(query)
        
        print(f"回答: {result.answer}")
        
        if result.rewritten_queries:
            print(f"改写查询: {result.rewritten_queries}")
        
        if result.citations:
            print(f"引用来源:")
            for citation in result.citations[:3]:
                print(f"  [{citation['id']}] {citation['content'][:100]}...")


def demo_chat(pipeline: DefaultRAGPipeline):
    """演示：多轮对话"""
    print("\n" + "=" * 60)
    print("步骤3: 多轮对话")
    print("=" * 60)
    
    session_id = "demo_session_001"
    
    conversations = [
        "RAG和微调有什么区别？",
        "它的缺点是什么？",
        "有什么解决方案？",
    ]
    
    for idx, query in enumerate(conversations, 1):
        print(f"\n用户 {idx}: {query}")
        
        result = pipeline.chat(
            query=query,
            session_id=session_id,
            use_memory=True
        )
        
        print(f"助手: {result.answer}")


def main():
    """主函数"""
    print("""
╔══════════════════════════════════════════════════════════════╗
║                   RAG 轻量级脚手架 - 快速开始                  ║
║                                                              ║
║  定位: 学习型开源项目，默认配置开箱即用                        ║
║  特点: 模块清晰，代码可读，可渐进升级到生产环境                ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    pipeline = demo_ingest()
    demo_query(pipeline)
    demo_chat(pipeline)
    
    print("\n" + "=" * 60)
    print("演示完成!")
    print("=" * 60)
    print("\n下一步:")
    print("  1. 替换示例文档为你自己的PDF/Markdown/TXT文件")
    print("  2. 调整RAGConfig配置参数")
    print("  3. 查看 src/rag/pipeline.py 了解底层实现")
    print("\nGitHub: https://github.com/JX-76/rag-enterprise-system")


if __name__ == "__main__":
    main()
