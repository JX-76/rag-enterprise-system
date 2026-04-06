"""
对话状态管理
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional
from enum import Enum


class DialogueState(Enum):
    """对话状态"""
    IDLE = "idle"           # 空闲
    LISTENING = "listening" # 倾听中
    THINKING = "thinking"   # 思考中
    RESPONDING = "responding"  # 回复中
    AWAITING_CONFIRMATION = "awaiting_confirmation"  # 等待确认
    ERROR = "error"         # 错误状态


@dataclass
class DialogueTurn:
    """对话轮次"""
    role: str  # user / assistant / system
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict = field(default_factory=dict)
    skill_calls: List[Dict] = field(default_factory=list)  # 技能调用记录


@dataclass
class DialogueSession:
    """对话会话"""
    session_id: str
    user_id: str
    state: DialogueState = DialogueState.IDLE
    turns: List[DialogueTurn] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: Dict = field(default_factory=dict)
    
    def add_turn(self, role: str, content: str, metadata: Dict = None):
        """添加对话轮次"""
        turn = DialogueTurn(
            role=role,
            content=content,
            metadata=metadata or {}
        )
        self.turns.append(turn)
        self.updated_at = datetime.now()
        
        # 限制历史长度
        if len(self.turns) > 50:
            self.turns = self.turns[-50:]
    
    def get_recent_turns(self, n: int = 10) -> List[DialogueTurn]:
        """获取最近n轮对话"""
        return self.turns[-n:]
    
    def to_messages(self) -> List[Dict]:
        """转换为消息格式"""
        return [
            {"role": t.role, "content": t.content}
            for t in self.turns
        ]


class DialogueManager:
    """对话管理器"""
    
    def __init__(self):
        self._sessions: Dict[str, DialogueSession] = {}
    
    def get_or_create_session(
        self,
        session_id: str,
        user_id: str
    ) -> DialogueSession:
        """获取或创建会话"""
        if session_id not in self._sessions:
            self._sessions[session_id] = DialogueSession(
                session_id=session_id,
                user_id=user_id
            )
        return self._sessions[session_id]
    
    def get_session(self, session_id: str) -> Optional[DialogueSession]:
        """获取会话"""
        return self._sessions.get(session_id)
    
    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        user_id: str = "",
        metadata: Dict = None
    ):
        """添加消息"""
        session = self.get_or_create_session(session_id, user_id)
        session.add_turn(role, content, metadata)
    
    def get_history(self, session_id: str, n: int = 10) -> List[Dict]:
        """获取对话历史"""
        session = self.get_session(session_id)
        if not session:
            return []
        return session.to_messages()[-n:]
    
    def set_state(self, session_id: str, state: DialogueState):
        """设置对话状态"""
        session = self.get_session(session_id)
        if session:
            session.state = state
    
    def clear_session(self, session_id: str):
        """清理会话"""
        if session_id in self._sessions:
            del self._sessions[session_id]
    
    def get_active_sessions(self) -> List[str]:
        """获取活跃会话"""
        return list(self._sessions.keys())
