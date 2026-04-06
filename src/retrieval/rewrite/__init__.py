"""
Query Rewriting Module - 查询改写模块
支持HyDE、Multi-Query、查询扩展、子问题拆解、会话感知改写
"""
from .hyde import HyDERewriter
from .multi_query import MultiQueryGenerator
from .expansion import QueryExpander
from .decomposition import QuestionDecomposer
from .session_aware import SessionAwareRewriter
from typing import List, Dict, Any, Optional
import asyncio
from src.core.logging import get_logger
from src.core.config import REWRITE_CONFIG

logger = get_logger(__name__)


class QueryRewriter:
    """
    统一查询改写接口
    整合多种改写策略
    """
    
    def __init__(self):
        """初始化所有改写器"""
        self.hyde = HyDERewriter() if REWRITE_CONFIG["hyde"]["enabled"] else None
        self.multi_query = MultiQueryGenerator() if REWRITE_CONFIG["multi_query"]["enabled"] else None
        self.expander = QueryExpander()
        self.decomposer = QuestionDecomposer()
        self.session_rewriter = SessionAwareRewriter()
    
    async def rewrite(
        self,
        query: str,
        conversation_id: Optional[str] = None,
        enable_hyde: bool = True,
        enable_multi_query: bool = True,
        enable_expansion: bool = True
    ) -> List[str]:
        """
        综合查询改写
        
        策略：
        1. 如果有会话历史，先进行会话感知改写
        2. 并行执行HyDE、Multi-Query、Query Expansion
        3. 合并所有改写结果
        
        Args:
            query: 原始查询
            conversation_id: 会话ID
            enable_hyde: 是否启用HyDE
            enable_multi_query: 是否启用Multi-Query
            enable_expansion: 是否启用查询扩展
            
        Returns:
            改写后的查询列表
        """
        rewritten_queries = []
        
        # 会话感知改写
        if conversation_id:
            session_query = await self.session_rewriter.rewrite(query, conversation_id)
            if session_query != query:
                logger.info(f"Session-aware rewrite: '{query}' -> '{session_query}'")
                query = session_query
        
        # 并行执行各种改写策略
        tasks = []
        
        if enable_hyde and self.hyde:
            tasks.append(self._hyde_rewrite(query))
        
        if enable_multi_query and self.multi_query:
            tasks.append(self._multi_query_rewrite(query))
        
        if enable_expansion:
            tasks.append(self._expansion_rewrite(query))
        
        # 等待所有改写完成
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 合并结果
        for result in results:
            if isinstance(result, Exception):
                logger.warning(f"Rewrite failed: {result}")
                continue
            rewritten_queries.extend(result)
        
        # 去重并保留原始查询
        unique_queries = self._deduplicate_queries([query] + rewritten_queries)
        
        logger.info(f"Query rewrite: '{query}' -> {len(unique_queries)} unique queries")
        return unique_queries
    
    async def _hyde_rewrite(self, query: str) -> List[str]:
        """HyDE改写"""
        try:
            hypothetical_doc = await self.hyde.generate(query)
            return [hypothetical_doc]
        except Exception as e:
            logger.warning(f"HyDE failed: {e}")
            return []
    
    async def _multi_query_rewrite(self, query: str) -> List[str]:
        """Multi-Query改写"""
        try:
            queries = await self.multi_query.generate(query)
            return queries
        except Exception as e:
            logger.warning(f"Multi-query failed: {e}")
            return []
    
    async def _expansion_rewrite(self, query: str) -> List[str]:
        """查询扩展"""
        try:
            expanded = await self.expander.expand(query)
            return [expanded] if expanded != query else []
        except Exception as e:
            logger.warning(f"Query expansion failed: {e}")
            return []
    
    def _deduplicate_queries(self, queries: List[str]) -> List[str]:
        """查询去重"""
        seen = set()
        unique = []
        for q in queries:
            q_lower = q.lower().strip()
            if q_lower not in seen:
                seen.add(q_lower)
                unique.append(q)
        return unique
