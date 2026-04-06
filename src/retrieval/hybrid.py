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
    
    优势：
    - 不需要归一化不同来源的分数
    - 对排名敏感，对绝对分数不敏感
    - 简单高效
    """
    
    def __init__(self, k: int = 60):
        self.k = k
    
    def fuse(
        self,
        results_lists: List[List[RetrievalResult]],
        weights: Optional[List[float]] = None
    ) -> List[RetrievalResult]:
        """
        融合多个检索结果列表
        
        Args:
            results_lists: 多个检索结果列表
            weights: 各列表的权重，默认为等权重
            
        Returns:
            融合后的排序结果
        """
        if not results_lists:
            return []
        
        if weights is None:
            weights = [1.0] * len(results_lists)
        
        # 收集所有文档及其RRF分数
        rrf_scores: Dict[str, float] = {}
        result_map: Dict[str, RetrievalResult] = {}
        
        for results, weight in zip(results_lists, weights):
            for rank, result in enumerate(results, start=1):
                doc_id = result.id
                
                # RRF分数计算
                rrf_score = weight * (1 / (self.k + rank))
                
                if doc_id in rrf_scores:
                    rrf_scores[doc_id] += rrf_score
                else:
                    rrf_scores[doc_id] = rrf_score
                    result_map[doc_id] = result
        
        # 按RRF分数排序
        sorted_results = sorted(
            rrf_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        # 构建结果列表
        fused_results = []
        for doc_id, score in sorted_results:
            result = result_map[doc_id]
            result.score = score
            fused_results.append(result)
        
        logger.debug(f"RRF fusion: {len(rrf_scores)} unique docs from {len(results_lists)} sources")
        return fused_results


class DenseRetriever:
    """稠密向量检索"""
    
    def __init__(self, vector_store=None, embedding_model=None):
        self.vector_store = vector_store
        self.embedding_model = embedding_model
    
    async def retrieve(
        self,
        query: str,
        top_k: int = 20
    ) -> List[RetrievalResult]:
        """稠密检索"""
        logger.debug(f"Dense retrieval: query='{query[:50]}...', top_k={top_k}")
        
        # 生成查询向量
        if self.embedding_model:
            query_vector = await self.embedding_model.embed(query)
        else:
            # Mock实现
            query_vector = np.random.randn(768)
        
        # 向量检索
        if self.vector_store:
            results = await self.vector_store.search(
                query_vector,
                top_k=top_k
            )
        else:
            # Mock结果
            results = [
                RetrievalResult(
                    id=f"dense_{i}",
                    content=f"Dense result {i} for {query[:30]}",
                    score=float(1.0 - i * 0.05),
                    source="dense",
                    metadata={}
                )
                for i in range(min(top_k, 10))
            ]
        
        return results


class SparseRetriever:
    """稀疏向量检索 (SPLADE等)"""
    
    def __init__(self, vector_store=None):
        self.vector_store = vector_store
    
    async def retrieve(
        self,
        query: str,
        top_k: int = 20
    ) -> List[RetrievalResult]:
        """稀疏检索"""
        logger.debug(f"Sparse retrieval: query='{query[:50]}...', top_k={top_k}")
        
        # Mock实现
        results = [
            RetrievalResult(
                id=f"sparse_{i}",
                content=f"Sparse result {i} for {query[:30]}",
                score=float(0.9 - i * 0.04),
                source="sparse",
                metadata={}
            )
            for i in range(min(top_k, 8))
        ]
        
        return results


class BM25Retriever:
    """BM25关键词检索"""
    
    def __init__(self, index=None):
        self.index = index
    
    async def retrieve(
        self,
        query: str,
        top_k: int = 20
    ) -> List[RetrievalResult]:
        """BM25检索"""
        logger.debug(f"BM25 retrieval: query='{query[:50]}...', top_k={top_k}")
        
        # Mock实现
        results = [
            RetrievalResult(
                id=f"bm25_{i}",
                content=f"BM25 result {i} for {query[:30]}",
                score=float(0.85 - i * 0.03),
                source="bm25",
                metadata={}
            )
            for i in range(min(top_k, 6))
        ]
        
        return results


class HybridRetriever:
    """
    混合检索器
    
    组合多种检索方式：
    - Dense: 语义匹配
    - Sparse: 关键词匹配
    - BM25: 传统关键词匹配
    
    使用RRF融合结果
    """
    
    def __init__(self, config=None):
        self.config = config or RETRIEVAL_CONFIG
        
        # 初始化各检索器
        self.dense_retriever = DenseRetriever()
        self.sparse_retriever = SparseRetriever()
        self.bm25_retriever = BM25Retriever()
        
        # 权重配置
        self.weights = {
            "dense": self.config.get("dense_weight", 0.4),
            "sparse": self.config.get("sparse_weight", 0.3),
            "bm25": self.config.get("bm25_weight", 0.3)
        }
        
        # RRF融合器
        self.fusion = RRFFusion(k=self.config.get("rrf_k", 60))
        
        logger.info(
            f"HybridRetriever initialized with weights: "
            f"dense={self.weights['dense']}, "
            f"sparse={self.weights['sparse']}, "
            f"bm25={self.weights['bm25']}"
        )
    
    async def retrieve(
        self,
        query: str,
        top_k: int = 20,
        enable_dense: bool = True,
        enable_sparse: bool = True,
        enable_bm25: bool = True
    ) -> List[RetrievalResult]:
        """
        执行混合检索
        
        Args:
            query: 查询文本
            top_k: 返回结果数
            enable_dense: 是否启用稠密检索
            enable_sparse: 是否启用稀疏检索
            enable_bm25: 是否启用BM25
            
        Returns:
            融合后的检索结果
        """
        logger.info(f"Hybrid retrieval: '{query[:50]}...'")
        
        # 并行执行多路检索
        tasks = []
        weights = []
        
        if enable_dense:
            tasks.append(self.dense_retriever.retrieve(query, top_k))
            weights.append(self.weights["dense"])
        
        if enable_sparse:
            tasks.append(self.sparse_retriever.retrieve(query, top_k))
            weights.append(self.weights["sparse"])
        
        if enable_bm25:
            tasks.append(self.bm25_retriever.retrieve(query, top_k))
            weights.append(self.weights["bm25"])
        
        # 等待所有检索完成
        results_lists = await asyncio.gather(*tasks)
        
        # RRF融合
        fused_results = self.fusion.fuse(results_lists, weights)
        
        logger.info(
            f"Hybrid retrieval complete: "
            f"{sum(len(r) for r in results_lists)} raw results -> "
            f"{len(fused_results)} fused results"
        )
        
        return fused_results[:top_k]
