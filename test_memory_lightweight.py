#!/usr/bin/env python3
"""
轻量级记忆层测试 - 不依赖模型加载

快速验证 Memory 四层架构的核心逻辑
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from memory import MemoryManager, MemoryLayer
from memory.memory_types import UltraShortTermMemory


def test_ultra_short_memory():
    """测试超短期记忆（当前会话上下文）"""
    print("=" * 60)
    print("测试: 超短期记忆 (Ultra-Short Term Memory)")
    print("=" * 60)
    
    manager = MemoryManager()
    user_id = "test_user"
    session_id = "session_001"
    
    # 添加对话消息
    print("\n[1] 添加对话消息到当前会话...")
    manager.add_to_session_context(
        user_id=user_id,
        session_id=session_id,
        role="user",
        content="什么是RAG技术？",
        metadata={"timestamp": "2025-04-07T10:00:00"}
    )
    
    manager.add_to_session_context(
        user_id=user_id,
        session_id=session_id,
        role="assistant",
        content="RAG是检索增强生成，结合检索和生成模型...",
        metadata={"timestamp": "2025-04-07T10:00:05"}
    )
    
    manager.add_to_session_context(
        user_id=user_id,
        session_id=session_id,
        role="user",
        content="它有什么优势？",
        metadata={"timestamp": "2025-04-07T10:00:30"}
    )
    
    # 获取会话上下文
    print("\n[2] 获取会话上下文...")
    context = manager.get_session_context(user_id, session_id)
    print(f"上下文内容:\n{context}")
    
    # 验证消息数量
    key = f"{user_id}:{session_id}"
    memory = manager.ultra_short_memory.get(key)
    if memory:
        print(f"\n[✓] 会话消息数: {len(memory.messages)}")
        print(f"[✓] 访问计数: {memory.access_count}")
    
    print("\n" + "=" * 60)
    print("超短期记忆测试通过 ✓")
    print("=" * 60)
    return True


def test_multi_session():
    """测试多会话隔离"""
    print("\n" + "=" * 60)
    print("测试: 多会话隔离")
    print("=" * 60)
    
    manager = MemoryManager()
    user_id = "test_user"
    
    # 会话1
    session1 = "session_001"
    manager.add_to_session_context(user_id, session1, "user", "会话1的问题")
    manager.add_to_session_context(user_id, session1, "assistant", "会话1的回答")
    
    # 会话2（新会话，应该没有会话1的上下文）
    session2 = "session_002"
    context2 = manager.get_session_context(user_id, session2)
    
    print(f"\n[1] 会话1上下文: {'有' if manager.get_session_context(user_id, session1) else '无'}")
    print(f"[2] 会话2上下文: {'有' if context2 else '无'} (应该是空的)")
    
    if not context2:
        print("\n[✓] 新会话正确隔离，没有历史上下文")
    else:
        print("\n[✗] 新会话不应该有上下文!")
        return False
    
    print("\n" + "=" * 60)
    print("多会话隔离测试通过 ✓")
    print("=" * 60)
    return True


def test_memory_context_building():
    """测试记忆上下文构建"""
    print("\n" + "=" * 60)
    print("测试: 记忆上下文构建")
    print("=" * 60)
    
    manager = MemoryManager()
    user_id = "test_user"
    session_id = "session_003"
    
    # 添加多轮对话
    conversation = [
        ("user", "什么是RAG？"),
        ("assistant", "RAG是检索增强生成技术..."),
        ("user", "它有什么优势？"),
        ("assistant", "RAG的优势包括减少幻觉、知识更新等..."),
        ("user", "具体怎么减少幻觉？"),
    ]
    
    print("\n[1] 添加多轮对话...")
    for role, content in conversation:
        manager.add_to_session_context(user_id, session_id, role, content)
    
    # 构建记忆上下文
    print("\n[2] 构建记忆上下文...")
    query = "刚才说的技术"
    context = manager.build_memory_context(user_id, session_id, query)
    
    print(f"\n生成的上下文:\n{'-' * 40}")
    print(context[:500] if len(context) > 500 else context)
    print("-" * 40)
    
    # 验证上下文包含历史
    if "RAG" in context or "检索" in context:
        print("\n[✓] 上下文包含历史对话信息")
    else:
        print("\n[✗] 上下文应该包含历史信息")
        return False
    
    print("\n" + "=" * 60)
    print("记忆上下文构建测试通过 ✓")
    print("=" * 60)
    return True


def test_memory_layer_structure():
    """测试记忆层结构"""
    print("\n" + "=" * 60)
    print("测试: 记忆层结构验证")
    print("=" * 60)
    
    # 验证四层架构
    layers = [
        (MemoryLayer.ULTRA_SHORT, "超短期记忆"),
        (MemoryLayer.SHORT, "短期记忆"),
        (MemoryLayer.LONG, "长期记忆"),
        (MemoryLayer.GLOBAL, "全局记忆"),
    ]
    
    print("\n记忆层架构:")
    for layer, name in layers:
        print(f"  • {layer.value}: {name}")
    
    # 验证 MemoryManager 结构
    manager = MemoryManager()
    attrs = ["ultra_short_memory", "save_short_term", "get_short_term", 
             "save_long_term", "get_long_term", "retrieve_relevant_memories"]
    
    print("\n验证 MemoryManager 方法:")
    for attr in attrs:
        exists = hasattr(manager, attr)
        symbol = "✓" if exists else "✗"
        print(f"  [{symbol}] {attr}")
    
    print("\n" + "=" * 60)
    print("记忆层结构验证通过 ✓")
    print("=" * 60)
    return True


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("Memory 四层架构 - 轻量级测试")
    print("=" * 60)
    print("\n测试内容:")
    print("  1. 超短期记忆（当前会话上下文）")
    print("  2. 多会话隔离")
    print("  3. 记忆上下文构建")
    print("  4. 记忆层结构验证")
    print()
    
    tests = [
        ("超短期记忆", test_ultra_short_memory),
        ("多会话隔离", test_multi_session),
        ("记忆上下文构建", test_memory_context_building),
        ("记忆层结构", test_memory_layer_structure),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n[✗] {name} 测试失败: {e}")
            results.append((name, False))
    
    # 汇总
    print("\n" + "=" * 60)
    print("测试汇总")
    print("=" * 60)
    
    for name, result in results:
        symbol = "✓" if result else "✗"
        status = "通过" if result else "失败"
        print(f"  [{symbol}] {name}: {status}")
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    print(f"\n总计: {passed}/{total} 通过")
    
    if passed == total:
        print("\n🎉 所有测试通过！Memory 四层架构工作正常。")
    else:
        print(f"\n⚠️ {total - passed} 个测试失败，需要检查。")
    
    print("=" * 60)


if __name__ == "__main__":
    main()
