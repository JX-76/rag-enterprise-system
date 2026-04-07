"""
Memory 四层架构模块

超短期记忆：当前会话上下文
短期记忆：近7天会话历史（Redis）
长期记忆：用户偏好、高频问题（PostgreSQL + 向量检索）
全局记忆：企业公共知识（向量数据库）
"""
# 使用相对导入，需要作为包导入
from .memory_manager import MemoryManager
from .memory_types import (
    Memory,
    UltraShortTermMemory,
    ShortTermMemory,
    LongTermMemory,
    GlobalMemory,
    MemoryLayer
)

__all__ = [
    'MemoryManager',
    'Memory',
    'UltraShortTermMemory',
    'ShortTermMemory',
    'LongTermMemory',
    'GlobalMemory',
    'MemoryLayer'
]
