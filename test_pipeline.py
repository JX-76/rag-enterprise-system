#!/usr/bin/env python3
"""
Pipeline集成测试
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from rag.pipeline import DefaultRAGPipeline, RAGConfig


def test_pipeline():
    """测试Pipeline"""
    print("=" * 60)
    print("测试 DefaultRAGPipeline")
    print("=" * 60)
    
    # 1. 创建Pipeline
    config = RAGConfig(
        chunk_size=300,
        chunk_overlap=50,
        top_k=3,
        use_local_llm=True
    )
    
    print("\n1. 初始化Pipeline...")
    pipeline = DefaultRAGPipeline(config)
    print("   ✓ Pipeline创建成功")
    
    # 2. 获取统计信息
    stats = pipeline.get_stats()
    print(f"   配置: {stats['config']}")
    
    # 3. 文档入库（使用示例文本）
    print("\n2. 文档入库测试...")
    
    # 创建临时文档
    import tempfile
    sample_text = """# RAG技术介绍

检索增强生成（RAG）是一种将检索技术与生成模型结合的方法。
它通过从外部知识库中检索相关信息，提升回答的准确性。

RAG的优势：
1. 减少幻觉
2. 知识可更新
3. 可解释性强
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        f.write(sample_text)
        temp_path = f.name
    
    result = pipeline.ingest_document(temp_path)
    
    if result.success:
        print(f"   ✓ 入库成功: {result.chunks_count}个分块")
    else:
        print(f"   ✗ 入库失败: {result.error}")
    
    import os
    os.unlink(temp_path)
    
    # 4. 向量库统计
    print(f"\n3. 向量库统计...")
    print(f"   文档数: {pipeline._vector_store.count()}")
    
    # 5. 查询测试
    print("\n4. 查询测试...")
    
    queries = [
        "什么是RAG？",
        "RAG有什么优势？",
    ]
    
    for query in queries:
        print(f"\n   查询: {query}")
        result = pipeline.query(query)
        print(f"   回答: {result.answer[:100]}...")
        print(f"   检索到: {len(result.retrieved_docs)}个文档")
    
    # 6. 对话测试
    print("\n5. 对话测试（带Memory）...")
    
    session_id = "test_session_001"
    
    conv = [
        "什么是RAG？",
        "它有什么优势？",  # 指代"RAG"
    ]
    
    for q in conv:
        print(f"\n   用户: {q}")
        result = pipeline.chat(
            query=q,
            session_id=session_id,
            use_memory=True
        )
        print(f"   助手: {result.answer[:100]}...")
        print(f"   有历史: {result.metadata.get('has_history', False)}")
    
    print("\n" + "=" * 60)
    print("测试完成!")
    print("=" * 60)


if __name__ == "__main__":
    test_pipeline()
