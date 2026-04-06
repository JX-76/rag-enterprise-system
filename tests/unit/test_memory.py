"""
Memory 模块单元测试
"""
import pytest
from datetime import datetime
from src.memory.memory_types import (
    Memory, MemoryLayer,
    UltraShortTermMemory, ShortTermMemory,
    LongTermMemory, GlobalMemory
)
from src.memory.memory_manager import MemoryManager


class TestMemoryTypes:
    """测试记忆类型"""
    
    def test_ultra_short_term_memory(self):
        """测试超短期记忆"""
        memory = UltraShortTermMemory(
            id="test:session1",
            user_id="user1",
            session_id="session1",
            layer=MemoryLayer.ULTRA_SHORT,
            content="",
            context_window=5
        )
        
        # 添加消息
        memory.add_message("user", "你好")
        memory.add_message("assistant", "您好！")
        
        assert len(memory.messages) == 2
        assert memory.messages[0]["role"] == "user"
        
        # 测试上下文
        context = memory.get_context()
        assert "user: 你好" in context
        assert "assistant: 您好！" in context
        
        # 测试窗口限制
        for i in range(10):
            memory.add_message("user", f"消息{i}")
        assert len(memory.messages) == 5  # 窗口大小
    
    def test_memory_serialization(self):
        """测试记忆序列化/反序列化"""
        original = ShortTermMemory(
            id="test:short:1",
            user_id="user1",
            session_id="session1",
            layer=MemoryLayer.SHORT,
            content="会话摘要",
            session_summary="摘要",
            key_entities=["实体1", "实体2"]
        )
        
        # 序列化
        data = original.to_dict()
        
        # 反序列化
        restored = Memory.from_dict(data)
        
        assert isinstance(restored, ShortTermMemory)
        assert restored.session_summary == "摘要"
        assert restored.key_entities == ["实体1", "实体2"]
    
    def test_long_term_memory_preferences(self):
        """测试长期记忆偏好"""
        memory = LongTermMemory(
            id="user1:profile",
            user_id="user1",
            layer=MemoryLayer.LONG,
            content=""
        )
        
        memory.update_preference("theme", "dark")
        memory.update_preference("language", "zh")
        
        assert memory.preferences["theme"] == "dark"
        assert memory.preferences["language"] == "zh"
        
        memory.add_frequent_topic("RAG")
        memory.add_frequent_topic("Agent")
        
        assert "RAG" in memory.frequent_topics


class TestMemoryManager:
    """测试记忆管理器"""
    
    def test_ultra_short_memory_management(self):
        """测试超短期记忆管理"""
        manager = MemoryManager()
        
        # 添加消息
        manager.add_to_session_context("user1", "session1", "user", "你好")
        manager.add_to_session_context("user1", "session1", "assistant", "您好！")
        
        # 获取上下文
        context = manager.get_session_context("user1", "session1")
        assert context is not None
        assert "你好" in context
        
        # 清理
        manager.clear_session_context("user1", "session1")
        context = manager.get_session_context("user1", "session1")
        assert context is None
    
    def test_retrieve_relevant_memories(self):
        """测试记忆检索"""
        manager = MemoryManager()
        
        # 添加超短期记忆
        manager.add_to_session_context("user1", "session1", "user", "搜索文档")
        
        # 检索
        memories = manager.retrieve_relevant_memories(
            "user1", "session1", "搜索文档"
        )
        
        assert MemoryLayer.ULTRA_SHORT in memories
        assert len(memories[MemoryLayer.ULTRA_SHORT]) == 1
        
        # 构建上下文
        context = manager.build_memory_context("user1", "session1", "搜索")
        assert "当前会话" in context
        assert "搜索文档" in context
