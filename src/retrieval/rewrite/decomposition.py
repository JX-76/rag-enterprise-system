"""
Question Decomposition - 问题分解
将复杂问题拆分为子问题
"""
from typing import List

from src.core.logging import get_logger

logger = get_logger(__name__)


class QuestionDecomposer:
    """
    问题分解器
    
    原理：
    1. 识别复杂的多跳问题
    2. 分解为多个子问题
    3. 分别检索后合并结果
    """
    
    def __init__(self, llm=None):
        self.llm = llm
    
    async def decompose(self, query: str) -> List[str]:
        """
        分解问题
        
        Args:
            query: 原始问题
            
        Returns:
            子问题列表
        """
        logger.debug(f"Decomposing: {query}")
        
        # 简化实现：检查是否为复杂问题
        if not self._is_complex(query):
            return [query]
        
        # 分解逻辑
        sub_questions = self._split_question(query)
        
        return sub_questions
    
    def _is_complex(self, query: str) -> bool:
        """判断是否为复杂问题"""
        # 检查关键词
        complex_indicators = ["和", "与", "以及", "对比", "区别", "如何"]
        return any(indicator in query for indicator in complex_indicators)
    
    def _split_question(self, query: str) -> List[str]:
        """拆分问题"""
        # 简化实现
        parts = []
        
        if "和" in query:
            parts = query.split("和")
        elif "与" in query:
            parts = query.split("与")
        else:
            parts = [query]
        
        return [p.strip() for p in parts if p.strip()]
