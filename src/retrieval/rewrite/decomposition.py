"""
Question Decomposition - 查询分解
将复杂问题拆分为子问题

核心思想：
- 复杂问题包含多个子问题
- 分别回答子问题，再合并答案
- 降低每个检索步骤的复杂度

参考论文: "Least-to-Most Prompting Enables Complex Reasoning in Large Language Models"
"""
from typing import List, Dict, Any, Optional
import asyncio

from src.core.logging import get_logger

logger = get_logger(__name__)


class DecompositionRewriter:
    """
    查询分解改写器
    
    使用场景：
    - 复杂的多跳问题
    - 需要多步推理的问题
    - 包含多个子问题的问题
    
    示例：
    输入："对比A公司和B公司的财务状况和市场份额"
    输出：["A公司的财务状况如何？", "B公司的财务状况如何？", 
           "A公司的市场份额是多少？", "B公司的市场份额是多少？"]
    
    优点：
    - 每个子问题更简单，检索更精准
    - 可并行处理子问题
    - 答案结构更清晰
    
    缺点：
    - 增加LLM调用成本
    - 需要有效的结果合并
    - 延迟增加
    """
    
    def __init__(self, llm_client=None, prompt_template: str = None):
        """
        初始化分解改写器
        
        Args:
            llm_client: LLM客户端
            prompt_template: 自定义prompt模板
        """
        self.llm = llm_client
        self.prompt_template = prompt_template or self._default_prompt()
        
        logger.info("DecompositionRewriter initialized")
    
    def _default_prompt(self) -> str:
        """默认prompt模板"""
        return """将复杂问题分解为2-4个简单子问题。

复杂问题：{query}

要求：
1. 每个子问题聚焦一个具体方面
2. 子问题之间要有逻辑顺序
3. 回答所有子问题就能回答原问题
4. 子问题应简洁明确
5. 直接列出子问题，每行一个

子问题："""
    
    async def rewrite(self, query: str) -> List[str]:
        """
        改写查询
        
        Args:
            query: 原始查询
            
        Returns:
            子问题列表（如果不需要分解，返回[query]）
        """
        logger.debug(f"Decomposition rewriting: '{query[:50]}...'")
        
        # 判断是否需要分解
        if not self._is_complex(query):
            logger.debug("Query is simple, no decomposition needed")
            return [query]
        
        # 分解问题
        sub_queries = await self._decompose(query)
        
        logger.debug(f"Decomposed into {len(sub_queries)} sub-queries")
        return sub_queries
    
    def _is_complex(self, query: str) -> bool:
        """
        判断问题复杂度
        
        复杂问题特征：
        - 包含多个疑问词
        - 长度较长
        - 包含对比/比较
        - 包含多个实体
        """
        # 有多个疑问词
        question_words = ["什么", "如何", "为什么", "哪些", "怎么", "多少"]
        count = sum(1 for w in question_words if w in query)
        
        # 对比词
        compare_words = ["对比", "比较", "区别", "差异", "vs", "versus"]
        has_compare = any(w in query for w in compare_words)
        
        # 和/与（可能表示多个对象）
        has_multi = "和" in query or "与" in query
        
        # 长度
        is_long = len(query) > 50
        
        return count >= 2 or has_compare or (has_multi and is_long)
    
    async def _decompose(self, query: str) -> List[str]:
        """
        分解问题
        
        Args:
            query: 原始查询
            
        Returns:
            子问题列表
        """
        if not self.llm:
            # Mock实现：基于规则分解
            return self._rule_based_decompose(query)
        
        try:
            prompt = self.prompt_template.format(query=query)
            
            response = await self.llm.generate(
                prompt,
                temperature=0.5,
                max_tokens=300
            )
            
            # 解析子问题
            sub_queries = [
                q.strip()
                for q in response.strip().split('\n')
                if q.strip() and '?' in q or '？' in q or len(q.strip()) > 10
            ]
            
            return sub_queries if sub_queries else [query]
            
        except Exception as e:
            logger.error(f"Failed to decompose query: {e}")
            return self._rule_based_decompose(query)
    
    def _rule_based_decompose(self, query: str) -> List[str]:
        """
        基于规则的简单分解（Mock）
        
        Args:
            query: 原始查询
            
        Returns:
            子问题列表
        """
        sub_queries = []
        
        # 对比类分解
        if "对比" in query or "比较" in query:
            # 提取对比对象（简化处理）
            parts = query.split("对比")
            if len(parts) == 2:
                aspect = parts[1].replace("如何", "").replace("怎么样", "").strip()
                sub_queries = [
                    f"{parts[0].strip()}的{aspect}是什么？",
                    f"{parts[1].strip()}的{aspect}是什么？"
                ]
        
        # 和/与分解
        elif "和" in query or "与" in query:
            separator = "和" if "和" in query else "与"
            parts = query.split(separator)
            if len(parts) == 2:
                prefix = query[:query.index(separator)].strip()
                suffix = query[query.index(separator) + 1:].strip()
                sub_queries = [
                    f"{prefix}是什么？",
                    f"{suffix}是什么？"
                ]
        
        # 默认：不分解
        if not sub_queries:
            sub_queries = [query]
        
        return sub_queries
    
    async def rewrite_batch(self, queries: List[str]) -> List[List[str]]:
        """批量改写"""
        tasks = [self.rewrite(q) for q in queries]
        return await asyncio.gather(*tasks)


class DecompositionWithAggregation(DecompositionRewriter):
    """
    分解 + 结果聚合
    
    不仅分解问题，还负责聚合子问题的答案
    """
    
    def __init__(self, llm_client=None):
        super().__init__(llm_client)
        self.aggregation_prompt = """基于以下子问题的回答，生成对原问题的完整答案。

原问题：{original_query}

子问题及回答：
{sub_answers}

要求：
1. 综合所有子问题的回答
2. 保持逻辑连贯
3. 直接回答原问题
4. 如果子问题回答有冲突，说明原因

完整答案："""
    
    async def aggregate_answers(
        self,
        original_query: str,
        sub_queries: List[str],
        sub_answers: List[str]
    ) -> str:
        """
        聚合子问题答案
        
        Args:
            original_query: 原问题
            sub_queries: 子问题列表
            sub_answers: 子问题答案列表
            
        Returns:
            聚合后的完整答案
        """
        if not self.llm or len(sub_queries) == 1:
            # 简单拼接
            return "\n\n".join(sub_answers)
        
        # 构建子问题-答案对
        qa_pairs = [
            f"Q{i+1}: {q}\nA{i+1}: {a}"
            for i, (q, a) in enumerate(zip(sub_queries, sub_answers))
        ]
        
        prompt = self.aggregation_prompt.format(
            original_query=original_query,
            sub_answers="\n\n".join(qa_pairs)
        )
        
        try:
            response = await self.llm.generate(
                prompt,
                temperature=0.3,
                max_tokens=500
            )
            return response.strip()
        except Exception as e:
            logger.error(f"Failed to aggregate answers: {e}")
            return "\n\n".join(sub_answers)


# 向后兼容
QuestionDecomposer = DecompositionRewriter