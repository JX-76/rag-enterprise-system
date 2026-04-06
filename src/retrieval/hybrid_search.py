"""
Hybrid Search - 多路混合检索

支持:
- Dense Retrieval (向量相似度)
- Sparse Retrieval (BM25)
- RRF (Reciprocal Rank Fusion) 融合
- 可配置权重
"""
import math
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)

# 尝试导入Whoosh
try:
    from whoosh.index import create_in, open_dir
    from whoosh.fields import Schema, TEXT, ID, STORED
    from whoosh.qparser import QueryParser
    from whoosh import scoring
    WHOOSH_AVAILABLE = True
except ImportError:
    WHOOSH_AVAILABLE = False
    create_in = open_dir = Schema = TEXT = ID = STORED = QueryParser = scoring = None


@dataclass
class SearchResult:
    """搜索结果"""
    id: str
    text: str
    score: float
    source: str  # 'dense', 'bm25', 'fusion'
    metadata: Dict[str, Any]
    rank: int = 0


@dataclass
class HybridSearchConfig:
    """混合检索配置"""
    # RRF参数
    rrf_k: int = 60  # RRF常数，通常60
    
    # 各检索器权重
    dense_weight: float = 0.5
    bm25_weight: float = 0.5
    
    # Top-K
    top_k: int = 10
    
    # BM25参数
    bm25_k1: float = 1.5
    bm25_b: float = 0.75


class BM25Retriever:
    """
    BM25稀疏检索
    
    基于Whoosh实现
    """
    
    def __init__(
        self,
        index_dir: str = "./bm25_index",
        k1: float = 1.5,
        b: float = 0.75
    ):
        self.index_dir = index_dir
        self.k1 = k1
        self.b = b
        self._index = None
        self._schema = None
        
        if not WHOOSH_AVAILABLE:
            logger.warning("whoosh not installed. BM25 retrieval disabled.")
    
    def _init_schema(self):
        """初始化schema"""
        if self._schema is None:
            self._schema = Schema(
                id=ID(stored=True, unique=True),
                text=TEXT(stored=True),
                metadata=STORED
            )
    
    def build_index(self, documents: List[Dict[str, Any]]):
        """
        构建索引
        
        Args:
            documents: [{"id": str, "text": str, "metadata": dict}, ...]
        """
        if not WHOOSH_AVAILABLE:
            raise ImportError("whoosh required")
        
        import os
        self._init_schema()
        
        # 创建目录
        os.makedirs(self.index_dir, exist_ok=True)
        
        # 创建索引
        self._index = create_in(self.index_dir, self._schema)
        writer = self._index.writer()
        
        for doc in documents:
            writer.add_document(
                id=doc["id"],
                text=doc["text"],
                metadata=doc.get("metadata", {})
            )
        
        writer.commit()
        logger.info(f"BM25 index built: {len(documents)} documents")
    
    def search(
        self,
        query: str,
        top_k: int = 10
    ) -> List[SearchResult]:
        """
        BM25搜索
        
        Args:
            query: 查询文本
            top_k: 返回结果数
        
        Returns:
            搜索结果列表
        """
        if not WHOOSH_AVAILABLE:
            raise ImportError("whoosh required")
        
        if self._index is None:
            # 尝试打开已有索引
            try:
                self._index = open_dir(self.index_dir)
            except:
                raise ValueError("Index not found. Call build_index first.")
        
        # 使用BM25评分
        bm25 = scoring.BM25F(K1=self.k1, B=self.b)
        
        with self._index.searcher(weighting=bm25) as searcher:
            parser = QueryParser("text", self._index.schema)
            q = parser.parse(query)
            
            results = searcher.search(q, limit=top_k)
            
            search_results = []
            for i, result in enumerate(results):
                search_results.append(SearchResult(
                    id=result["id"],
                    text=result["text"],
                    score=float(result.score),
                    source="bm25",
                    metadata=result["metadata"],
                    rank=i + 1
                ))
            
            return search_results


class DenseRetriever:
    """
    Dense向量检索
    
    基于ChromaDB
    """
    
    def __init__(self, vector_store):
        """
        Args:
            vector_store: VectorStore实例
        """
        self.vector_store = vector_store
    
    def search(
        self,
        query_embedding: List[float],
        top_k: int = 10
    ) -> List[SearchResult]:
        """
        向量搜索
        
        Args:
            query_embedding: 查询向量
            top_k: 返回结果数
        
        Returns:
            搜索结果列表
        """
        results = self.vector_store.search(
            query_embedding=query_embedding,
            top_k=top_k
        )
        
        search_results = []
        for i, r in enumerate(results):
            # ChromaDB返回的是distance，转为similarity
            # cosine distance -> similarity
            score = 1.0 - r["score"] if r["score"] <= 1.0 else 0.0
            
            search_results.append(SearchResult(
                id=r["id"],
                text=r["text"],
                score=score,
                source="dense",
                metadata=r["metadata"],
                rank=i + 1
            ))
        
        return search_results


class HybridRetriever:
    """
    混合检索器
    
    融合Dense和BM25结果
    """
    
    def __init__(
        self,
        dense_retriever: Optional[DenseRetriever] = None,
        bm25_retriever: Optional[BM25Retriever] = None,
        config: Optional[HybridSearchConfig] = None
    ):
        self.dense_retriever = dense_retriever
        self.bm25_retriever = bm25_retriever
        self.config = config or HybridSearchConfig()
    
    def search(
        self,
        query: str,
        query_embedding: Optional[List[float]] = None,
        top_k: Optional[int] = None
    ) -> List[SearchResult]:
        """
        混合搜索
        
        Args:
            query: 查询文本
            query_embedding: 查询向量（用于Dense检索）
            top_k: 返回结果数
        
        Returns:
            融合后的搜索结果
        """
        top_k = top_k or self.config.top_k
        
        # 收集各路结果
        dense_results = []
        bm25_results = []
        
        if self.dense_retriever and query_embedding:
            try:
                dense_results = self.dense_retriever.search(
                    query_embedding,
                    top_k=top_k * 2  # 多取一些用于融合
                )
            except Exception as e:
                logger.warning(f"Dense search failed: {e}")
        
        if self.bm25_retriever:
            try:
                bm25_results = self.bm25_retriever.search(
                    query,
                    top_k=top_k * 2
                )
            except Exception as e:
                logger.warning(f"BM25 search failed: {e}")
        
        # RRF融合
        if dense_results or bm25_results:
            fused = self._rrf_fusion(
                dense_results,
                bm25_results,
                top_k
            )
            return fused
        
        return []
    
    def _rrf_fusion(
        self,
        dense_results: List[SearchResult],
        bm25_results: List[SearchResult],
        top_k: int
    ) -> List[SearchResult]:
        """
        RRF (Reciprocal Rank Fusion) 融合
        
        公式: score = Σ(1 / (k + rank))
        """
        k = self.config.rrf_k
        
        # 收集所有文档的RRF分数
        rrf_scores = defaultdict(float)
        doc_info = {}
        
        # Dense结果
        for r in dense_results:
            rrf_scores[r.id] += self.config.dense_weight / (k + r.rank)
            if r.id not in doc_info:
                doc_info[r.id] = r
        
        # BM25结果
        for r in bm25_results:
            rrf_scores[r.id] += self.config.bm25_weight / (k + r.rank)
            if r.id not in doc_info:
                doc_info[r.id] = r
        
        # 排序
        sorted_ids = sorted(
            rrf_scores.keys(),
            key=lambda x: rrf_scores[x],
            reverse=True
        )[:top_k]
        
        # 构建结果
        fused_results = []
        for rank, doc_id in enumerate(sorted_ids, 1):
            info = doc_info[doc_id]
            fused_results.append(SearchResult(
                id=doc_id,
                text=info.text,
                score=rrf_scores[doc_id],
                source="fusion",
                metadata={
                    **info.metadata,
                    "dense_score": next(
                        (r.score for r in dense_results if r.id == doc_id), None
                    ),
                    "bm25_score": next(
                        (r.score for r in bm25_results if r.id == doc_id), None
                    )
                },
                rank=rank
            ))
        
        return fused_results


# 便捷函数
def create_hybrid_retriever(
    vector_store=None,
    bm25_index_dir: str = "./bm25_index",
    rrf_k: int = 60,
    dense_weight: float = 0.5,
    bm25_weight: float = 0.5
) -> HybridRetriever:
    """
    创建混合检索器
    
    Args:
        vector_store: 向量存储实例
        bm25_index_dir: BM25索引目录
        rrf_k: RRF常数
        dense_weight: Dense检索权重
        bm25_weight: BM25检索权重
    
    Returns:
        HybridRetriever实例
    """
    config = HybridSearchConfig(
        rrf_k=rrf_k,
        dense_weight=dense_weight,
        bm25_weight=bm25_weight
    )
    
    dense_retriever = DenseRetriever(vector_store) if vector_store else None
    bm25_retriever = BM25Retriever(bm25_index_dir) if WHOOSH_AVAILABLE else None
    
    return HybridRetriever(
        dense_retriever=dense_retriever,
        bm25_retriever=bm25_retriever,
        config=config
    )
