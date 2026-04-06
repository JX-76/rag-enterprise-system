"""
Multi-Query Generator - 多角度查询生成
"""
from typing import List
import re

from src.core.logging import get_logger

logger = get_logger(__name__)


class MultiQueryGenerator:
    """
    Multi-Query生成器
    
    原理：
    1. 从原始查询生成多个相关查询
    2. 每个查询从略微不同的角度提问
    3. 合并多个查询的检索结果
    """
    
    def __init__(self, llm=None, num_queries: int = 5):
        self.llm = llm
        self.num_queries = num_queries
        self.prompt_template = """请针对以下问题生成{num}个不同的查询变体。

原始问题：{query}

请生成{num}个从不同角度表达的查询（每行一个）：
"""
    
    async def generate(self, query: str) -> List[str]:
        """
        生成多查询
        
        Args:
            query: 原始查询
            
        Returns:
            查询列表
        """
        prompt = self.prompt_template.format(
            query=query,
            num=self.num_queries
        )
        
        logger.debug(f"Generating {self.num_queries} queries for: {query}")
        
        # 简化实现
        if self.llm:
            response = await self.llm.generate(prompt)
            return self._parse_queries(response)
        
        # Mock实现
        return self._generate_mock_queries(query)
    
    def _parse_queries(self, response: str) -> List[str]:
        """解析生成的查询"""
        lines = response.strip().split('\n')
        queries = []
        
        for line in lines:
            # 去除序号和标记
            line = re.sub(r'^\d+[.、)\]]\s*', '', line)
            line = line.strip()
            
            if line and len(line) > 5:
                queries.append(line)
        
        return queries[:self.num_queries]
    
    def _generate_mock_queries(self, query: str) -> List[str]:
        """生成Mock查询"""
        return [
            f"{query}是什么",
            f"{query}的原理",
            f"{query}的应用",
            f"{query}的优势",
            f"{query}的案例"
        ][:self.num_queries]
