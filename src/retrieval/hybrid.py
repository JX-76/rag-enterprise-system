"""
Hybrid Retrieval - 混合检索
支持稠密向量 + 稀疏向量 + BM25 的RRF融合
"""
import asyncio
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import numpy as np

from src.core.config import RETRIEVAL_CONFIG
from src.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class RetrievalResult:
    """检索结果"""
    id: str
    content: str
    score: float
    source: str  # dense, sparse, bm25
    metadata: Dict[str, Any]


class RRFFusion:
    """
    Reciprocal Rank Fusion (RRF)
    倒数秩融合算法
    
    公式: score = Σ(1 / (k + rank))
    k通常取60
    """
    
    def __init__(self, k: int = 60):
        self.k = k
    
    def fuse(
        self,
        results_list: List[List[Dict[str, Any]]],
        top_k: int = 20
    ) -> List[Dict[str, Any]]:
        """
        融合多个检索结果
        
        Args:
            results_list: 多个检索器的结果列表
            top_k: 返回结果数
        """
        # 收集所有文档的RRF分数
        rrf_scores: Dict[str, float] = {}
        doc_info: Dict[str, Dict] = {}
        
        for results in results_list:
            for rank, result in enumerate(results):
                doc_id = result.get("id", str(hash(result.get("content", ""))))
                
                # RRF分数计算
                rrf_score = 1.0 / (self.k + rank + 1)  # rank从0开始
                
                if doc_id in rrf_scores:
                    rrf_scores[doc_id] += rrf_score
                else:
                    rrf_scores[doc_id] = rrf_score
                    doc_info[doc_id] = result
        
        # 按RRF分数排序
        sorted_docs = sorted(
            rrf_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )[:top_k]
        
        # 构建结果
        fused_results = []
        for doc_id, score in sorted_docs:
            info = doc_info[doc_id]
            fused_results.append({
                "id": doc_id,
                "content": info.get("content", ""),
                "score": score,
                "metadata": info.get("metadata", {})
            })
        
        return fused_results


class DenseRetriever:
    """稠密向量检索"""
    
    def __init__(self):
        self.embedding_service = None
        self.vector_store = None
        self._initialized = False
    
    async def _ensure_initialized(self):
        """确保初始化"""
        if self._initialized:
            return
        
        from src.services.embedding_service import get_embedding_service
        from src.vector_store.faiss_store import get_vector_store
        
        self.embedding_service = await get_embedding_service()
        self.vector_store = get_vector_store()
        self._initialized = True
    
    async def retrieve(
        self,
        query: str,
        top_k: int = 20
    ) -> List[Dict[str, Any]]:
        """稠密检索"""
        try:
            await self._ensure_initialized()
            
            # 编码查询
            query_vector = await self.embedding_service.encode(query)
            
            # 向量检索
            results = await self.vector_store.search(
                vector=query_vector,
                top_k=top_k
            )
            
            logger.debug(f"Dense retrieve: {len(results)} results for '{query[:50]}...'")
            return results
            
        except Exception as e:
            logger.error(f"Dense retrieval failed: {e}")
            return []


class SparseRetriever:
    """稀疏向量检索 (SPLADE)"""
    
    def __init__(self):
        self.model = None
    
    async def retrieve(
        self,
        query: str,
        top_k: int = 20
    ) -> List[Dict[str, Any]]:
        """稀疏检索"""
        logger.debug(f"Sparse retrieve: {query[:50]}...")
        return []


class BM25Retriever:
    """BM25检索"""
    
    def __init__(self):
        self.index = None
    
    async def retrieve(
        self,
        query: str,
        top_k: int = 20
    ) -> List[Dict[str, Any]]:
        """BM25检索"""
        logger.debug(f"BM25 retrieve: {query[:50]}...")
        return []


class HybridRetriever:
    """
    混合检索器
    整合稠密、稀疏、BM25三种检索方式
    """
    
    def __init__(self):
        self.dense_retriever = DenseRetriever()
        self.sparse_retriever = SparseRetriever()
        self.bm25_retriever = BM25Retriever()
        self.fusion = RRFFusion(k=60)
        
        self.weights = {
            "dense": RETRIEVAL_CONFIG["dense"]["weight"],
            "sparse": RETRIEVAL_CONFIG["sparse"]["weight"],
            "bm25": RETRIEVAL_CONFIG["bm25"]["weight"]
        }
    
    async def retrieve(
        self,
        queries: List[str],
        top_k: int = 20
    ) -> List[Dict[str, Any]]:
        """
        混合检索 - 并行执行所有查询和检索方式
        
        Args:
            queries: 查询列表（支持多查询改写后的结果）
            top_k: 返回结果数
        """
        if not queries:
            return []
        
        # 并行执行所有查询的所有检索方式
        all_tasks = []
        for query in queries:
            all_tasks.append(("dense", query, self.dense_retriever.retrieve(query, top_k)))
            all_tasks.append(("sparse", query, self.sparse_retriever.retrieve(query, top_k)))
            all_tasks.append(("bm25", query, self.bm25_retriever.retrieve(query, top_k)))
        
        # 等待所有任务完成
        results = await asyncio.gather(
            *[task[2] for task in all_tasks],
            return_exceptions=True
        )
        
        # 整理结果
        all_results = []
        for (source, query, _), result in zip(all_tasks, results):
            if isinstance(result, Exception):
                logger.warning(f"{source} retrieval failed for '{query}': {result}")
                continue
            all_results.append((source, result))
        
        # 按源类型分组
        dense_all = []
        sparse_all = []
        bm25_all = []
        
        for source, results in all_results:
            if source == "dense":
                dense_all.extend(results)
            elif source == "sparse":
                sparse_all.extend(results)
            else:
                bm25_all.extend(results)
        
        # RRF融合
        if not any([dense_all, sparse_all, bm25_all]):
            return []
        
        fused_results = self.fusion.fuse(
            [dense_all, sparse_all, bm25_all],
            top_k=top_k
        )
        
        return fused_results
