"""
Multi-Query Expansion - 多查询扩展
生成多个查询变体，提高召回率

核心思想：
- 同一意图可以有多种表达方式
- 不同角度的查询能召回不同文档
- 用多个查询覆盖更大的文档空间

参考论文: "Query Expansion Techniques for Information Retrieval"
"""
from typing import List
import asyncio
import re

from src.core.logging import get_logger

logger = get_logger(__name__)


class MultiQueryRewriter:
    """
    多查询改写器
    
    使用场景：
    - 需要高召回率的场景
    - 用户查询表述单一
    - 文档集合表达多样化
    
    优点：
    - 显著提升召回率
    - 无需额外训练
    
    缺点：
    - 增加检索成本（多次检索）
    - 可能引入噪声
    - 需要有效的结果融合
    """
    
    def __init__(self, llm_client=None, num_queries: int = 5, prompt_template: str = None):
        """
        初始化多查询改写器
        
        Args:
            llm_client: LLM客户端
            num_queries: 生成的查询数量
            prompt_template: 自定义prompt模板
        """
        self.llm = llm_client
        self.num_queries = num_queries
        self.prompt_template = prompt_template or self._default_prompt()
        
        logger.info(f"MultiQueryRewriter initialized (num_queries={num_queries})")
    
    def _default_prompt(self) -> str:
        """默认prompt模板"""
        return """从多个角度改写用户问题，生成{num_queries}个不同的查询。

原问题：{query}

要求：
1. 保持原意，但使用不同表述方式
2. 每个查询聚焦不同角度或关键词
3. 查询应简洁明确，适合检索
4. 直接列出查询，每行一个，不要编号和解释

生成的查询："""
    
    async def rewrite(self, query: str) -> List[str]:
        """
        改写查询
        
        Args:
            query: 原始查询
            
        Returns:
            改写后的查询列表（包含原查询）
        """
        logger.debug(f"Multi-query rewriting: '{query[:50]}...'")
        
        # 生成多个查询
        generated_queries = await self._generate_queries(query)
        
        # 合并结果（原查询 + 生成查询）
        all_queries = [query] + generated_queries
        
        # 去重
        unique_queries = []
        seen = set()
        for q in all_queries:
            q_normalized = q.lower().strip()
            if q_normalized not in seen:
                seen.add(q_normalized)
                unique_queries.append(q)
        
        logger.debug(f"Generated {len(unique_queries)} unique queries")
        return unique_queries[:self.num_queries + 1]  # +1 for original
    
    async def _generate_queries(self, query: str) -> List[str]:
        """生成多个查询变体"""
        if not self.llm:
            # Mock实现：基于规则生成简单变体
            return self._rule_based_variants(query)
        
        try:
            prompt = self.prompt_template.format(
                query=query,
                num_queries=self.num_queries
            )
            
            response = await self.llm.generate(
                prompt,
                temperature=0.8,
                max_tokens=200
            )
            
            # 解析生成的查询
            queries = [
                q.strip()
                for q in response.strip().split('\n')
                if q.strip() and len(q.strip()) > 5
            ]
            
            return queries[:self.num_queries]
            
        except Exception as e:
            logger.error(f"Failed to generate queries: {e}")
            return self._rule_based_variants(query)
    
    def _rule_based_variants(self, query: str) -> List[str]:
        """基于规则的简单变体生成（Mock）"""
        variants = []
        
        # 添加"什么是"前缀
        if not query.startswith('什么'):
            variants.append(f"什么是{query}？")
        
        # 添加"如何"前缀
        variants.append(f"如何{query}？")
        
        # 添加"为什么"前缀
        variants.append(f"为什么{query}？")
        
        # 添加"...的方法"
        variants.append(f"{query}的方法")
        
        return variants[:self.num_queries]
    
    async def rewrite_batch(self, queries: List[str]) -> List[List[str]]:
        """批量改写"""
        tasks = [self.rewrite(q) for q in queries]
        return await asyncio.gather(*tasks)


class MultiQueryWithFusion(MultiQueryRewriter):
    """
    多查询 + 结果融合
    
    不仅生成多个查询，还负责融合多个查询的检索结果
    """
    
    def __init__(self, llm_client=None, num_queries: int = 3, fusion_k: int = 60):
        super().__init__(llm_client, num_queries)
        self.fusion_k = fusion_k
    
    def fuse_results(self, results_lists: List[List[dict]]) -> List[dict]:
        """
        融合多个查询的检索结果（RRF）
        
        Args:
            results_lists: 多个查询的检索结果列表
            
        Returns:
            融合后的排序结果
        """
        from collections import defaultdict
        
        rrf_scores = defaultdict(float)
        doc_map = {}
        
        for results in results_lists:
            for rank, doc in enumerate(results, start=1):
                doc_id = doc.get('id', str(hash(doc.get('content', ''))))
                
                # RRF分数
                rrf_score = 1 / (self.fusion_k + rank)
                rrf_scores[doc_id] += rrf_score
                
                if doc_id not in doc_map:
                    doc_map[doc_id] = doc
        
        # 排序
        sorted_docs = sorted(
            rrf_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        return [doc_map[doc_id] for doc_id, _ in sorted_docs]
