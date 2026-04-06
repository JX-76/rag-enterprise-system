"""
Session-Aware Rewriting - 会话感知改写
利用对话历史优化当前查询
"""
from typing import Optional, List, Dict, Any

from src.core.logging import get_logger

logger = get_logger(__name__)


class SessionAwareRewriter:
    """
    会话感知改写器
    
    原理：
    1. 维护对话历史
    2. 识别指代和省略
    3. 补全上下文，生成完整查询
    """
    
    def __init__(self):
        # 简化：内存存储会话历史
        # 实际应使用Redis或数据库
        self.sessions: Dict[str, List[Dict]] = {}
    
    async def rewrite(
        self,
        query: str,
        conversation_id: str
    ) -> str:
        """
        会话感知改写
        
        Args:
            query: 当前查询
            conversation_id: 会话ID
            
        Returns:
            改写后的查询
        """
        history = self._get_history(conversation_id)
        
        if not history:
            return query
        
        # 检查是否需要改写（指代、省略）
        if self._needs_rewrite(query):
            rewritten = self._rewrite_with_context(query, history)
            logger.debug(f"Session rewrite: '{query}' -> '{rewritten}'")
            return rewritten
        
        return query
    
    def add_turn(
        self,
        conversation_id: str,
        query: str,
        answer: str
    ):
        """添加对话轮次"""
        if conversation_id not in self.sessions:
            self.sessions[conversation_id] = []
        
        self.sessions[conversation_id].append({
            "query": query,
            "answer": answer
        })
        
        # 保留最近10轮
        self.sessions[conversation_id] = self.sessions[conversation_id][-10:]
    
    def _get_history(self, conversation_id: str) -> List[Dict]:
        """获取会话历史"""
        return self.sessions.get(conversation_id, [])
    
    def _needs_rewrite(self, query: str) -> bool:
        """判断是否需要改写"""
        indicators = ["它", "这个", "那个", "为什么", "怎么", "呢"]
        return any(ind in query for ind in indicators) or len(query) < 10
    
    def _rewrite_with_context(
        self,
        query: str,
        history: List[Dict]
    ) -> str:
        """结合上下文改写"""
        # 简化实现：拼接历史主题
        if not history:
            return query
        
        last_query = history[-1]["query"]
        
        # 简单补全
        if "它" in query or "这个" in query:
            return f"关于'{last_query}'，{query}"
        
        return query
