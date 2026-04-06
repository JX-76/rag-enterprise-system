"""
Advanced Retrieval - 基于RAG_Techniques的高级检索策略
- 查询改写 (Query Rewriting)
- 多跳检索 (Multi-hop)
- 假设文档嵌入 (HyDE)
"""
from typing import List, Dict, Any, Optional
import asyncio
import numpy as np

from src.core.logging import get_logger

logger = get_logger(__name__)


class QueryRewriter:
    """
    查询改写器
    基于RAG_Techniques的多种改写策略
    """
    
    def __init__(self, llm_client=None):
        self.llm = llm_client
        self.strategies = {
            "hyde": self._hyde_rewrite,
            "expansion": self._expansion_rewrite,
            "decomposition": self._decomposition_rewrite,
            "multi_query": self._multi_query_rewrite,
        }
    
    async def rewrite(
        self,
        query: str,
        strategy: str = "hyde",
        **kwargs
    ) -> List[str]:
        """
        改写查询
        
        Returns:
            List[str]: 改写后的查询列表（多查询）
        """
        if strategy not in self.strategies:
            logger.warning(f"Unknown strategy {strategy}, using hyde")
            strategy = "hyde"
        
        return await self.strategies[strategy](query, **kwargs)
    
    async def _hyde_rewrite(self, query: str, num_docs: int = 3) -> List[str]:
        """
        HyDE (Hypothetical Document Embeddings)
        生成假设文档作为查询
        """
        if not self.llm:
            # Fallback: 返回原查询
            return [query]
        
        prompt = f"""Generate {num_docs} hypothetical documents that would answer this query.
Query: {query}

Documents:"""
        
        try:
            response = await self.llm.generate(prompt)
            # 解析生成的文档
            docs = self._parse_generated_docs(response)
            return [query] + docs  # 保留原查询
        except Exception as e:
            logger.error(f"HyDE failed: {e}")
            return [query]
    
    async def _expansion_rewrite(self, query: str, expansions: int = 3) -> List[str]:
        """
        查询扩展：生成相关查询
        """
        if not self.llm:
            return [query]
        
        prompt = f"""Generate {expansions} different ways to ask this question:
Query: {query}

Variations:"""
        
        try:
            response = await self.llm.generate(prompt)
            variations = self._parse_list(response)
            return [query] + variations
        except Exception as e:
            logger.error(f"Expansion failed: {e}")
            return [query]
    
    async def _decomposition_rewrite(self, query: str) -> List[str]:
        """
        查询分解：将复杂查询拆分为子查询
        """
        if not self.llm:
            return [query]
        
        prompt = f"""Break down this complex query into simpler sub-queries:
Query: {query}

Sub-queries:"""
        
        try:
            response = await self.llm.generate(prompt)
            sub_queries = self._parse_list(response)
            return sub_queries if sub_queries else [query]
        except Exception as e:
            logger.error(f"Decomposition failed: {e}")
            return [query]
    
    async def _multi_query_rewrite(self, query: str, num_queries: int = 3) -> List[str]:
        """
        多角度查询：从不同角度问同一个问题
        """
        if not self.llm:
            return [query]
        
        prompt = f"""Generate {num_queries} different questions that would help answer:
Query: {query}

Questions:"""
        
        try:
            response = await self.llm.generate(prompt)
            queries = self._parse_list(response)
            return [query] + queries
        except Exception as e:
            logger.error(f"Multi-query failed: {e}")
            return [query]
    
    def _parse_generated_docs(self, text: str) -> List[str]:
        """解析生成的文档"""
        # 简单分割，实际可以更复杂
        docs = []
        for line in text.strip().split('\n'):
            line = line.strip()
            if line and not line.startswith('Document'):
                docs.append(line)
        return docs[:5]  # 最多5个
    
    def _parse_list(self, text: str) -> List[str]:
        """解析列表"""
        items = []
        for line in text.strip().split('\n'):
            line = line.strip()
            # 移除序号标记
            if line:
                line = line.lstrip('0123456789.-) ')
                if line:
                    items.append(line)
        return items


class MultiHopRetriever:
    """
    多跳检索器
    基于RAG_Techniques的迭代检索策略
    """
    
    def __init__(self, base_retriever, llm_client=None):
        self.retriever = base_retriever
        self.llm = llm_client
        self.max_hops = 3
    
    async def retrieve(
        self,
        query: str,
        top_k: int = 5,
        max_hops: int = 3
    ) -> List[Dict[str, Any]]:
        """
        多跳检索
        
        流程：
        1. 检索初始文档
        2. 分析是否需要更多信息
        3. 生成子查询继续检索
        4. 整合所有结果
        """
        all_results = []
        visited_ids = set()
        
        current_query = query
        
        for hop in range(max_hops):
            logger.info(f"Multi-hop retrieval: hop {hop + 1}/{max_hops}")
            
            # 检索
            results = await self.retriever.retrieve(current_query, top_k=top_k)
            
            # 去重
            new_results = []
            for r in results:
                doc_id = r.get("id", hash(r.get("content", "")))
                if doc_id not in visited_ids:
                    visited_ids.add(doc_id)
                    new_results.append(r)
            
            all_results.extend(new_results)
            
            # 检查是否需要继续
            if hop < max_hops - 1 and self.llm:
                need_more = await self._need_more_info(query, new_results)
                if not need_more:
                    break
                
                # 生成下一个查询
                current_query = await self._generate_follow_up(query, new_results)
        
        # 重排序整合结果
        return self._merge_results(all_results, query, top_k)
    
    async def _need_more_info(
        self,
        original_query: str,
        current_results: List[Dict]
    ) -> bool:
        """判断是否需要更多信息"""
        if not self.llm or len(current_results) == 0:
            return False
        
        context = "\n".join([r.get("content", "")[:200] for r in current_results[:3]])
        
        prompt = f"""Based on the retrieved information, can we fully answer the question?
If not, we need to search for more information.

Question: {original_query}

Retrieved Information:
{context}

Can we answer? (Yes/No):"""
        
        try:
            response = await self.llm.generate(prompt)
            return "no" in response.lower()
        except:
            return False
    
    async def _generate_follow_up(
        self,
        original_query: str,
        current_results: List[Dict]
    ) -> str:
        """生成后续查询"""
        if not self.llm:
            return original_query
        
        context = "\n".join([r.get("content", "")[:200] for r in current_results[:3]])
        
        prompt = f"""The current information is incomplete. What specific information should we search for next?

Original Question: {original_query}
Current Information: {context}

Next search query:"""
        
        try:
            response = await self.llm.generate(prompt)
            return response.strip() or original_query
        except:
            return original_query
    
    def _merge_results(
        self,
        results: List[Dict],
        query: str,
        top_k: int
    ) -> List[Dict]:
        """合并并排序结果"""
        # 简单去重并返回top-k
        seen = set()
        merged = []
        for r in results:
            content = r.get("content", "")
            key = hash(content[:100])  # 内容指纹
            if key not in seen:
                seen.add(key)
                merged.append(r)
        
        # 按相关性分数排序（如果有）
        merged.sort(key=lambda x: x.get("score", 0), reverse=True)
        
        return merged[:top_k]


class FusionRetriever:
    """
    融合检索器
    结合多种检索策略的结果
    """
    
    def __init__(self, retrievers: Dict[str, Any]):
        self.retrievers = retrievers
        self.weights = {name: 1.0 for name in retrievers}
    
    async def retrieve(
        self,
        query: str,
        top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """
        融合多种检索器的结果
        """
        all_results = []
        
        # 并行执行所有检索器
        tasks = []
        for name, retriever in self.retrievers.items():
            tasks.append(self._retrieve_with_name(name, retriever, query, top_k))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, Exception):
                logger.warning(f"Retriever failed: {result}")
                continue
            all_results.extend(result)
        
        # 融合排序
        return self._fuse_results(all_results, top_k)
    
    async def _retrieve_with_name(
        self,
        name: str,
        retriever: Any,
        query: str,
        top_k: int
    ) -> List[Dict]:
        """带名称标记的检索"""
        results = await retriever.retrieve(query, top_k=top_k)
        for r in results:
            r["retriever"] = name
        return results
    
    def _fuse_results(
        self,
        results: List[Dict],
        top_k: int
    ) -> List[Dict]:
        """RRF融合"""
        k = 60
        scores = {}
        doc_info = {}
        
        # 按检索器分组
        by_retriever = {}
        for r in results:
            name = r.get("retriever", "unknown")
            if name not in by_retriever:
                by_retriever[name] = []
            by_retriever[name].append(r)
        
        # 计算RRF分数
        for name, retriever_results in by_retriever.items():
            weight = self.weights.get(name, 1.0)
            for rank, result in enumerate(retriever_results):
                doc_id = result.get("id", hash(result.get("content", "")))
                score = weight * (1.0 / (k + rank + 1))
                
                if doc_id in scores:
                    scores[doc_id] += score
                else:
                    scores[doc_id] = score
                    doc_info[doc_id] = result
        
        # 排序
        sorted_docs = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        
        return [doc_info[doc_id] for doc_id, _ in sorted_docs[:top_k]]
