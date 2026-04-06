"""
Query Rewriter - 查询改写模块

支持策略:
- Multi-Query: 生成多个查询变体
- HyDE (Hypothetical Document Embeddings): 生成假设答案再检索
"""
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class RewrittenQuery:
    """改写后的查询"""
    query: str
    strategy: str  # 'multi_query', 'hyde', 'original'
    weight: float = 1.0
    metadata: Dict[str, Any] = None


class QueryRewriter:
    """
    查询改写器
    
    使用示例:
        rewriter = QueryRewriter()
        queries = rewriter.rewrite("什么是机器学习？", strategies=['multi_query'])
    """
    
    def __init__(self, llm_client=None):
        self.llm_client = llm_client
    
    def rewrite(
        self,
        query: str,
        strategies: List[str] = None,
        num_variations: int = 3
    ) -> List[RewrittenQuery]:
        """
        改写查询
        
        Args:
            query: 原始查询
            strategies: 改写策略列表 ['multi_query', 'hyde']
            num_variations: 变体数量
        
        Returns:
            改写后的查询列表
        """
        strategies = strategies or ['multi_query']
        results = []
        
        # 原始查询
        results.append(RewrittenQuery(
            query=query,
            strategy='original',
            weight=1.0
        ))
        
        if 'multi_query' in strategies:
            multi_queries = self._generate_multi_query(query, num_variations)
            results.extend(multi_queries)
        
        if 'hyde' in strategies:
            hyde_query = self._generate_hyde(query)
            if hyde_query:
                results.append(hyde_query)
        
        return results
    
    def _generate_multi_query(
        self,
        query: str,
        num: int = 3
    ) -> List[RewrittenQuery]:
        """
        生成多查询变体
        
        不依赖LLM的规则实现
        """
        variations = []
        
        # 策略1: 去除疑问词
        no_question = re.sub(r'^(什么是|什么是|请问|我想知道)\s*', '', query)
        if no_question != query:
            variations.append(RewrittenQuery(
                query=no_question,
                strategy='multi_query',
                weight=0.9,
                metadata={'type': 'remove_question_word'}
            ))
        
        # 策略2: 提取关键词
        words = re.findall(r'[\u4e00-\u9fa5a-zA-Z]+', query)
        if len(words) > 2:
            keywords = ' '.join(words[-2:])  # 取最后两个词
            variations.append(RewrittenQuery(
                query=keywords,
                strategy='multi_query',
                weight=0.8,
                metadata={'type': 'keywords'}
            ))
        
        # 策略3: 同义词替换（简单规则）
        synonyms = {
            '机器学习': ['machine learning', 'ML'],
            '深度学习': ['deep learning', 'DL'],
            '人工智能': ['AI', 'artificial intelligence'],
            '神经网络': ['neural network', 'NN']
        }
        
        for term, alts in synonyms.items():
            if term in query:
                for alt in alts[:1]:  # 只取一个替代
                    new_query = query.replace(term, alt, 1)
                    if new_query != query:
                        variations.append(RewrittenQuery(
                            query=new_query,
                            strategy='multi_query',
                            weight=0.85,
                            metadata={'type': 'synonym', 'original': term}
                        ))
                        break
        
        # 策略4: 补充上下文
        if '如何' in query or '怎么' in query:
            expanded = f"{query} 步骤 方法 教程"
            variations.append(RewrittenQuery(
                query=expanded,
                strategy='multi_query',
                weight=0.7,
                metadata={'type': 'expand_context'}
            ))
        
        return variations[:num]
    
    def _generate_hyde(self, query: str) -> Optional[RewrittenQuery]:
        """
        生成HyDE查询
        
        HyDE策略: 假设文档嵌入
        - 生成一个假设的答案文档
        - 用这个文档去检索
        
        当前使用简单模板实现，有LLM时可增强
        """
        # 简单的HyDE模拟：扩展查询为"答案形式"
        hyde_doc = f"关于{query}，主要内容包括定义、原理、应用场景和实现方法。"
        
        return RewrittenQuery(
            query=hyde_doc,
            strategy='hyde',
            weight=0.8,
            metadata={'type': 'hypothetical_document'}
        )


class LLMQueryRewriter(QueryRewriter):
    """
    基于LLM的查询改写器
    
    需要LLM客户端支持
    """
    
    def _generate_multi_query(
        self,
        query: str,
        num: int = 3
    ) -> List[RewrittenQuery]:
        """
        使用LLM生成多查询变体
        """
        if not self.llm_client:
            # 降级到规则实现
            return super()._generate_multi_query(query, num)
        
        try:
            prompt = f"""为以下查询生成{num}个不同表达的变体，保持语义相同：

查询: {query}

要求:
1. 改变句式或用词
2. 可以是指令式、疑问式或陈述式
3. 每个变体一行
4. 不要解释，只输出变体

变体:"""
            
            response = self.llm_client.generate(prompt)
            lines = [l.strip() for l in response.split('\n') if l.strip()]
            
            variations = []
            for i, line in enumerate(lines[:num]):
                variations.append(RewrittenQuery(
                    query=line,
                    strategy='multi_query',
                    weight=0.9 - i * 0.1,
                    metadata={'type': 'llm_generated', 'index': i}
                ))
            
            return variations
        except Exception as e:
            logger.warning(f"LLM multi-query failed: {e}")
            return super()._generate_multi_query(query, num)
    
    def _generate_hyde(self, query: str) -> Optional[RewrittenQuery]:
        """
        使用LLM生成HyDE文档
        """
        if not self.llm_client:
            return super()._generate_hyde(query)
        
        try:
            prompt = f"""为以下查询生成一个简短的假设性答案（50字以内）：

查询: {query}

请直接输出答案内容，不要加任何前缀。"""
            
            response = self.llm_client.generate(prompt)
            response = response.strip()
            
            if len(response) > 10:
                return RewrittenQuery(
                    query=response,
                    strategy='hyde',
                    weight=0.85,
                    metadata={'type': 'llm_generated_hyde'}
                )
        except Exception as e:
            logger.warning(f"LLM HyDE failed: {e}")
        
        return super()._generate_hyde(query)
