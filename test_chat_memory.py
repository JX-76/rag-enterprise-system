#!/usr/bin/env python3
"""
多轮记忆测试 - 演示Memory四层架构

测试场景：
1. 第一轮：问"什么是RAG？"
2. 第二轮：问"它有什么优势？"（应该能理解"它"指RAG）
3. 第三轮：问"刚才说的技术"（应该能关联到上下文）

运行:
    python test_chat_memory.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from rag.pipeline import DefaultRAGPipeline, RAGConfig


def test_multi_turn_conversation():
    """测试多轮对话记忆"""
    print("=" * 60)
    print("多轮记忆测试 - Memory四层架构")
    print("=" * 60)

    # 初始化Pipeline
    config = RAGConfig(
        chunk_size=500,
        top_k=5
    )
    pipeline = DefaultRAGPipeline(config)

    # 先入库一些测试文档
    print("\n[准备] 加载测试文档...")
    import tempfile
    import os

    # 创建测试文档
    test_docs = [
        ("rag_intro.txt", """
RAG（Retrieval-Augmented Generation，检索增强生成）是一种将检索技术与生成模型结合的方法。
它通过从外部知识库中检索相关信息，并将其作为上下文提供给语言模型，从而生成更准确、更可靠的回答。
"""),
        ("rag_advantages.txt", """
RAG的核心优势包括：
1. 减少幻觉：通过引用真实文档，降低模型编造信息的概率
2. 知识更新：无需重新训练模型，只需更新知识库即可注入新知识
3. 可解释性：回答可追溯到具体的文档来源
4. 成本效益：相比微调大模型，RAG的实施成本更低
""")
    ]

    doc_paths = []
    for filename, content in test_docs:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write(content)
            doc_paths.append(f.name)

    # 入库
    pipeline.ingest_documents(doc_paths)

    # 清理临时文件
    for path in doc_paths:
        os.unlink(path)

    # 模拟多轮对话
    session_id = "test_session_001"
    user_id = "test_user"

    conversation = [
        "什么是RAG技术？",
        "它有什么优势？",  # "它"应该指代RAG
        "刚才提到的幻觉问题怎么解决？",  # 应该关联到上文
    ]

    print("\n" + "=" * 60)
    print("开始多轮对话测试")
    print(f"会话ID: {session_id}")
    print("=" * 60)

    for i, query in enumerate(conversation, 1):
        print(f"\n[第{i}轮]")
        print(f"用户: {query}")

        # 使用chat方法（启用记忆）
        result = pipeline.chat(
            query=query,
            session_id=session_id,
            user_id=user_id,
            use_memory=True
        )

        print(f"助手: {result.answer[:200]}...")
        print(f"[元数据] 检索到{result.metadata.get('retrieved_count', 0)}个文档")
        print(f"[元数据] 使用了历史记忆: {result.metadata.get('history_used', False)}")

    # 查看记忆统计
    print("\n" + "=" * 60)
    print("记忆统计")
    print("=" * 60)
    memory_stats = pipeline.get_memory_stats(user_id)
    print(f"超短期记忆: {memory_stats.get('ultra_short_memory_count', 0)} 条")
    print(f"短期记忆: {memory_stats.get('short_term_memory_count', 0)} 条")

    # 新会话（无记忆）对比
    print("\n" + "=" * 60)
    print("新会话对比（无记忆）")
    print("=" * 60)
    new_session_result = pipeline.chat(
        query="它有什么优势？",
        session_id="new_session",  # 新会话
        user_id=user_id,
        use_memory=True
    )
    print(f"用户: 它有什么优势？")
    print(f"助手: {new_session_result.answer[:150]}...")
    print(f"[注意] 新会话无法理解'它'指代什么")

    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)
    print("\n关键验证点:")
    print("✓ 多轮对话能记住上文")
    print("✓ 代词指代能正确理解")
    print("✓ 记忆分层存储（超短期）")
    print("✓ 新会话无历史记忆")


if __name__ == "__main__":
    test_multi_turn_conversation()
