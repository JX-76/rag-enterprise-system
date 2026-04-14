"""
Query Rewriting Module - 查询改写模块
支持HyDE、Multi-Query、查询扩展、子问题拆解、会话感知改写
"""
from .hyde import HyDERewriter
from .multi_query import MultiQueryRewriter
from .expansion import QueryExpander
from .decomposition import QuestionDecomposer
from .session_aware import SessionAwareRewriter
from typing import List, Optional
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
        self.multi_query = MultiQueryRewriter(
            num_queries=REWRITE_CONFIG["multi_query"].get("num_queries", 5)
        ) if REWRITE_CONFIG["multi_query"]["enabled"] else None
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
        """
        rewritten_queries = []
        
        # 会话感知改写
        if conversation_id:
            session_query = await self.session_rewriter.rewrite(query, conversation_id)
            if session_query != query:
                logger.info(f"Session-aware rewrite: '{query}' -> '{session_query}'")
                query = session_query
        
        tasks = []
        if enable_hyde and self.hyde:
            tasks.append(self._hyde_rewrite(query))
        if enable_multi_query and self.multi_query:
            tasks.append(self._multi_query_rewrite(query))
        if enable_expansion:
            tasks.append(self._expansion_rewrite(query))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, Exception):
                logger.warning(f"Rewrite failed: {result}")
                continue
            rewritten_queries.extend(result)
        
        unique_queries = self._deduplicate_queries([query] + rewritten_queries)
        logger.info(f"Query rewrite: '{query}' -> {len(unique_queries)} unique queries")
        return unique_queries
    
    async def _hyde_rewrite(self, query: str) -> List[str]:
        try:
            return await self.hyde.rewrite(query)
        except Exception as e:
            logger.warning(f"HyDE failed: {e}")
            return []
    
    async def _multi_query_rewrite(self, query: str) -> List[str]:
        try:
            return await self.multi_query.rewrite(query)
        except Exception as e:
            logger.warning(f"Multi-query failed: {e}")
            return []
    
    async def _expansion_rewrite(self, query: str) -> List[str]:
        try:
            expanded = await self.expander.expand(query)
            return [expanded] if expanded != query else []
        except Exception as e:
            logger.warning(f"Query expansion failed: {e}")
            return []
    
    def _deduplicate_queries(self, queries: List[str]) -> List[str]:
        seen = set()
        unique = []
        for q in queries:
            q_lower = q.lower().strip()
            if q_lower not in seen:
                seen.add(q_lower)
                unique.append(q)
        return unique
