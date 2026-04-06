"""
Memory 数据类型定义
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional, Any
from enum import Enum
import json


class MemoryLayer(Enum):
    """记忆层级"""
    ULTRA_SHORT = "ultra_short"      # 超短期：当前会话
    SHORT = "short"                   # 短期：近7天
    LONG = "long"                     # 长期：用户画像
    GLOBAL = "global"                 # 全局：企业知识


@dataclass
class Memory:
    """记忆基类"""
    id: str
    user_id: str
    session_id: Optional[str]
    layer: MemoryLayer
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    embedding: Optional[List[float]] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    access_count: int = 0  # 访问次数，用于遗忘策略
    importance_score: float = 1.0  # 重要性分数

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'user_id': self.user_id,
            'session_id': self.session_id,
            'layer': self.layer.value,
            'content': self.content,
            'metadata': self.metadata,
            'embedding': self.embedding,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'access_count': self.access_count,
            'importance_score': self.importance_score
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Memory':
        """从字典创建记忆对象
        
        注意：子类需要重写此方法以处理额外字段
        """
        # 根据layer类型创建对应子类实例
        layer = MemoryLayer(data['layer'])
        
        if layer == MemoryLayer.SHORT:
            return ShortTermMemory.from_dict(data)
        elif layer == MemoryLayer.LONG:
            return LongTermMemory.from_dict(data)
        elif layer == MemoryLayer.GLOBAL:
            return GlobalMemory.from_dict(data)
        
        # 默认创建基类
        return cls(
            id=data['id'],
            user_id=data['user_id'],
            session_id=data.get('session_id'),
            layer=layer,
            content=data['content'],
            metadata=data.get('metadata', {}),
            embedding=data.get('embedding'),
            created_at=datetime.fromisoformat(data['created_at']),
            updated_at=datetime.fromisoformat(data['updated_at']),
            access_count=data.get('access_count', 0),
            importance_score=data.get('importance_score', 1.0)
        )


@dataclass
class UltraShortTermMemory(Memory):
    """超短期记忆：当前会话上下文"""
    messages: List[Dict[str, str]] = field(default_factory=list)  # 消息列表
    context_window: int = 10  # 上下文窗口大小

    def __post_init__(self):
        if self.layer is None:
            self.layer = MemoryLayer.ULTRA_SHORT

    def add_message(self, role: str, content: str, metadata: dict = None):
        """添加消息"""
        self.messages.append({
            'role': role,
            'content': content,
            'timestamp': datetime.now().isoformat(),
            'metadata': metadata or {}
        })
        # 保持窗口大小
        if len(self.messages) > self.context_window:
            self.messages = self.messages[-self.context_window:]
        self.updated_at = datetime.now()

    def get_context(self) -> str:
        """获取上下文字符串"""
        return "\n".join([
            f"{msg['role']}: {msg['content']}"
            for msg in self.messages
        ])


@dataclass
class ShortTermMemory(Memory):
    """短期记忆：近7天会话历史"""
    session_summary: str = ""  # 会话摘要
    key_entities: List[str] = field(default_factory=list)  # 关键实体
    task_history: List[Dict] = field(default_factory=list)  # 任务执行记录

    def __post_init__(self):
        if self.layer is None:
            self.layer = MemoryLayer.SHORT

    @classmethod
    def from_dict(cls, data: dict) -> 'ShortTermMemory':
        """从字典创建短期记忆"""
        return cls(
            id=data['id'],
            user_id=data['user_id'],
            session_id=data.get('session_id'),
            layer=MemoryLayer(data['layer']),
            content=data['content'],
            metadata=data.get('metadata', {}),
            embedding=data.get('embedding'),
            created_at=datetime.fromisoformat(data['created_at']),
            updated_at=datetime.fromisoformat(data['updated_at']),
            access_count=data.get('access_count', 0),
            importance_score=data.get('importance_score', 1.0),
            session_summary=data.get('session_summary', ''),
            key_entities=data.get('key_entities', []),
            task_history=data.get('task_history', [])
        )

    def add_task_record(self, task_type: str, status: str, result: str):
        """添加任务记录"""
        self.task_history.append({
            'task_type': task_type,
            'status': status,
            'result': result,
            'timestamp': datetime.now().isoformat()
        })
        # 只保留最近20条
        if len(self.task_history) > 20:
            self.task_history = self.task_history[-20:]


@dataclass
class LongTermMemory(Memory):
    """长期记忆：用户画像和偏好"""
    user_profile: Dict[str, Any] = field(default_factory=dict)  # 用户画像
    preferences: Dict[str, Any] = field(default_factory=dict)  # 偏好设置
    frequent_topics: List[str] = field(default_factory=list)  # 高频话题
    knowledge_gaps: List[str] = field(default_factory=list)  # 知识盲区
    domain_expertise: str = ""  # 专业领域
    response_style: str = "professional"  # 回答风格

    def __post_init__(self):
        if self.layer is None:
            self.layer = MemoryLayer.LONG

    @classmethod
    def from_dict(cls, data: dict) -> 'LongTermMemory':
        """从字典创建长期记忆"""
        return cls(
            id=data['id'],
            user_id=data['user_id'],
            session_id=data.get('session_id'),
            layer=MemoryLayer(data['layer']),
            content=data['content'],
            metadata=data.get('metadata', {}),
            embedding=data.get('embedding'),
            created_at=datetime.fromisoformat(data['created_at']),
            updated_at=datetime.fromisoformat(data['updated_at']),
            access_count=data.get('access_count', 0),
            importance_score=data.get('importance_score', 1.0),
            user_profile=data.get('user_profile', {}),
            preferences=data.get('preferences', {}),
            frequent_topics=data.get('frequent_topics', []),
            knowledge_gaps=data.get('knowledge_gaps', []),
            domain_expertise=data.get('domain_expertise', ''),
            response_style=data.get('response_style', 'professional')
        )

    def update_preference(self, key: str, value: Any):
        """更新偏好"""
        self.preferences[key] = value
        self.updated_at = datetime.now()

    def add_frequent_topic(self, topic: str):
        """添加高频话题"""
        if topic not in self.frequent_topics:
            self.frequent_topics.append(topic)
        if len(self.frequent_topics) > 50:
            self.frequent_topics = self.frequent_topics[-50:]


@dataclass
class GlobalMemory(Memory):
    """全局记忆：企业公共知识"""
    category: str = ""  # 知识分类
    source: str = ""  # 来源
    version: str = "1.0"  # 版本
    approved: bool = False  # 是否已审核
    tags: List[str] = field(default_factory=list)

    def __post_init__(self):
        if self.layer is None:
            self.layer = MemoryLayer.GLOBAL

    @classmethod
    def from_dict(cls, data: dict) -> 'GlobalMemory':
        """从字典创建全局记忆"""
        return cls(
            id=data['id'],
            user_id=data['user_id'],
            session_id=data.get('session_id'),
            layer=MemoryLayer(data['layer']),
            content=data['content'],
            metadata=data.get('metadata', {}),
            embedding=data.get('embedding'),
            created_at=datetime.fromisoformat(data['created_at']),
            updated_at=datetime.fromisoformat(data['updated_at']),
            access_count=data.get('access_count', 0),
            importance_score=data.get('importance_score', 1.0),
            category=data.get('category', ''),
            source=data.get('source', ''),
            version=data.get('version', '1.0'),
            approved=data.get('approved', False),
            tags=data.get('tags', [])
        )
