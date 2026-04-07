"""
混合检索模块 - Dense + BM25 + RRF融合
解决单一检索策略的局限性
"""
import math
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class RetrievalResult:
    """检索结果"""
    id: str
    text: str
    score: float
    source: str  # "dense" or "bm25"
    metadata: Dict[str, Any]


class BM25Index:
    """简单的BM25索引"""
    
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.documents = {}
        self.term_freq = {}
        self.doc_freq = {}
        self.doc_lengths = {}
        self.avg_doc_length = 0
        self.N = 0
    
    def add_documents(self, docs: Dict[str, str]):
        """添加文档"""
        for doc_id, text in docs.items():
            self.documents[doc_id] = text
            tokens = self._tokenize(text)
            self.doc_lengths[doc_id] = len(tokens)
            
            # 词频统计
            freq = {}
            for token in tokens:
                freq[token] = freq.get(token, 0) + 1
            
            self.term_freq[doc_id] = freq
            
            # 文档频率
            for token in set(tokens):
                self.doc_freq[token] = self.doc_freq.get(token, 0) + 1
        
        # 计算平均长度
        if self.doc_lengths:
            self.avg_doc_length = sum(self.doc_lengths.values()) / len(self.doc_lengths)
        self.N = len(self.documents)
        logger.info(f"BM25索引: {self.N} 文档")
    
    def _tokenize(self, text: str) -> List[str]:
        """分词（简单实现）"""
        import jieba
        tokens = list(jieba.cut(text))
        # 过滤停用词和短词
        return [t.strip() for t in tokens if len(t.strip()) > 1]
    
    def search(self, query: str, top_k: int = 10) -> List[RetrievalResult]:
        """BM25检索"""
        query_tokens = self._tokenize(query)
        scores = {}
        
        for doc_id in self.documents:
            score = self._bm25_score(doc_id, query_tokens)
            if score > 0:
                scores[doc_id] = score
        
        # 排序
        sorted_docs = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
        
        results = []
        for doc_id, score in sorted_docs:
            results.append(RetrievalResult(
                id=doc_id,
                text=self.documents[doc_id][:500],  # 截断
                score=score,
                source="bm25",
                metadata={}
            ))
        
        return results
    
    def _bm25_score(self, doc_id: str, query_tokens: List[str]) -> float:
        """计算BM25分数"""
        if not query_tokens:
            return 0
        
        score = 0
        doc_len = self.doc_lengths[doc_id]
        
        for token in query_tokens:
            if token not in self.term_freq[doc_id]:
                continue
            
            # IDF
            df = self.doc_freq.get(token, 0)
            idf = math.log((self.N - df + 0.5) / (df + 0.5) + 1)
            
            # TF
            tf = self.term_freq[doc_id][token]
            tf_weight = tf * (self.k1 + 1) / (tf + self.k1 * (1 - self.b + self.b * doc_len / self.avg_doc_length))
            
            score += idf * tf_weight
        
        return score


class HybridRetriever:
    """
    混合检索器
    
    结合：
    1. Dense向量检索 - 语义匹配
    2. BM25关键词检索 - 精确匹配
    3. RRF融合 - 综合排序
    """
    
    def __init__(
        self,
        vector_store,
        bm25_index: Optional[BM25Index] = None,
        dense_weight: float = 0.5,
        bm25_weight: float = 0.5,
        rrf_k: int = 60
    ):
        """
        Args:
            vector_store: 向量数据库
            bm25_index: BM25索引
            dense_weight: 向量检索权重
            bm25_weight: BM25权重
            rrf_k: RRF融合参数
        """
        self.vector_store = vector_store
        self.bm25_index = bm25_index
        self.dense_weight = dense_weight
        self.bm25_weight = bm25_weight
        self.rrf_k = rrf_k
        
        logger.info(f"混合检索器初始化: Dense={dense_weight}, BM25={bm25_weight}")
    
    def retrieve(
        self,
        query: str,
        query_embedding: List[float],
        top_k: int = 5
    ) -> List[RetrievalResult]:
        """
        混合检索
        
        Args:
            query: 查询文本
            query_embedding: 查询向量
            top_k: 返回结果数
        
        Returns:
            融合后的检索结果
        """
        results = []
        
        # Dense检索
        if self.vector_store and self.dense_weight > 0:
            try:
                dense_results = self._dense_search(query_embedding, top_k * 2)
                results.extend([("dense", r) for r in dense_results])
            except Exception as e:
                logger.error(f"Dense检索失败: {e}")
        
        # BM25检索
        if self.bm25_index and self.bm25_weight > 0:
            try:
                bm25_results = self.bm25_index.search(query, top_k * 2)
                results.extend([("bm25", r) for r in bm25_results])
            except Exception as e:
                logger.error(f"BM25检索失败: {e}")
        
        # RRF融合
        fused_results = self._rrf_fuse(results, top_k)
        
        logger.info(f"检索完成: {len(fused_results)} 结果")
        return fused_results
    
    def _dense_search(self, query_embedding: List[float], top_k: int) -> List[RetrievalResult]:
        """向量检索"""
        from ..vector.base import SearchResult
        
        search_results = self.vector_store.search(query_embedding, top_k)
        
        return [RetrievalResult(
            id=r.id,
            text=r.text,
            score=r.score,
            source="dense",
            metadata=r.metadata
        ) for r in search_results]
    
    def _rrf_fuse(
        self,
        results: List[tuple],
        top_k: int
    ) -> List[RetrievalResult]:
        """
        RRF (Reciprocal Rank Fusion) 融合
        
        score = sum(1 / (k + rank)) for each list
        """
        # 按source分组
        dense_results = [r for s, r in results if s == "dense"]
        bm25_results = [r for s, r in results if s == "bm25"]
        
        # 计算RRF分数
        rrf_scores = {}
        
        # Dense分数
        for rank, result in enumerate(dense_results, 1):
            doc_id = result.id
            score = self.dense_weight * (1 / (self.rrf_k + rank))
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + score
            rrf_scores[doc_id + "_text"] = result.text
            rrf_scores[doc_id + "_meta"] = result.metadata
        
        # BM25分数
        for rank, result in enumerate(bm25_results, 1):
            doc_id = result.id
            score = self.bm25_weight * (1 / (self.rrf_k + rank))
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + score
            if doc_id + "_text" not in rrf_scores:
                rrf_scores[doc_id + "_text"] = result.text
                rrf_scores[doc_id + "_meta"] = result.metadata
        
        # 排序
        sorted_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)[:top_k]
        
        # 构建结果
        fused_results = []
        for doc_id in sorted_ids:
            if not doc_id.endswith("_text") and not doc_id.endswith("_meta"):
                fused_results.append(RetrievalResult(
                    id=doc_id,
                    text=rrf_scores.get(doc_id + "_text", ""),
                    score=rrf_scores[doc_id],
                    source="hybrid",
                    metadata=rrf_scores.get(doc_id + "_meta", {})
                ))
        
        return fused_results


def create_retriever(vector_store, enable_bm25: bool = True) -> HybridRetriever:
    """创建检索器"""
    bm25_index = BM25Index() if enable_bm25 else None
    return HybridRetriever(vector_store, bm25_index)
