"""
Query Expansion - 查询扩展
"""
from typing import Optional

from src.core.logging import get_logger

logger = get_logger(__name__)


class QueryExpander:
    """
    查询扩展器
    
    原理：
    1. 识别查询中的关键词
    2. 添加同义词或相关词
    3. 扩大检索覆盖面
    """
    
    def __init__(self):
        self.synonyms = {
            "RAG": ["检索增强生成", "Retrieval-Augmented Generation"],
            "LLM": ["大模型", "大语言模型", "Large Language Model"],
            "优化": ["改进", "提升", "调优", "optimization"],
            "检索": ["搜索", "查询", "查找", "search"],
        }
    
    async def expand(self, query: str) -> str:
        """
        扩展查询
        
        Args:
            query: 原始查询
            
        Returns:
            扩展后的查询
        """
        expanded_terms = [query]
        
        # 查找同义词
        for term, synonyms in self.synonyms.items():
            if term in query:
                expanded_terms.extend(synonyms)
        
        # 合并
        expanded = " ".join(expanded_terms)
        
        logger.debug(f"Query expanded: '{query}' -> '{expanded}'")
        
        return expanded
