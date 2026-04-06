"""
RAG Engine - 核心RAG引擎
整合查询改写、多路检索、重排序、生成的完整流程
"""
import asyncio
from typing import List, Dict, Any, Optional
import time

from src.retrieval.rewrite import QueryRewriter
from src.retrieval.hybrid import HybridRetriever
from src.rerank.three_stage import ThreeStageReranker
from src.generation.generator import LLMGenerator
from src.core.logging import get_logger
from src.core.config import settings
from src.core.monitoring import metrics

logger = get_logger(__name__)


class RAGEngine:
    """企业级RAG引擎"""
    
    def __init__(self):
        """初始化RAG引擎组件"""
        logger.info("Initializing RAG Engine...")
        
        # 查询改写器
        self.rewriter = QueryRewriter()
        logger.info("✓ Query rewriter initialized")
        
        # 混合检索器
        self.retriever = HybridRetriever()
        logger.info("✓ Hybrid retriever initialized")
        
        # 三阶重排序器
        self.reranker = ThreeStageReranker()
        logger.info("✓ Three-stage reranker initialized")
        
        # LLM生成器
        self.generator = LLMGenerator()
        logger.info("✓ LLM generator initialized")
        
        logger.info("RAG Engine initialized successfully")
    
    async def query(
        self,
        query: str,
        conversation_id: Optional[str] = None,
        top_k: int = 5,
        rewrite: bool = True,
        rerank: bool = True
    ) -> Dict[str, Any]:
        """
        完整RAG查询流程
        
        Args:
            query: 用户查询
            conversation_id: 会话ID（多轮对话）
            top_k: 返回结果数量
            rewrite: 是否启用查询改写
            rerank: 是否启用重排序
            
        Returns:
            包含答案、来源、改写查询的结果
        """
        start_time = time.time()
        logger.info(f"Processing query: {query}")
        
        # Step 1: 查询改写
        rewritten_queries = []
        if rewrite:
            rewritten_queries = await self.rewriter.rewrite(
                query, 
                conversation_id=conversation_id
            )
            logger.info(f"Generated {len(rewritten_queries)} rewritten queries")
        else:
            rewritten_queries = [query]
        
        # Step 2: 多路检索
        retrieval_start = time.time()
        retrieval_results = await self.retriever.retrieve(
            queries=rewritten_queries,
            top_k=settings.RETRIEVAL_TOP_K
        )
        retrieval_time = (time.time() - retrieval_start) * 1000
        logger.info(f"Retrieval completed in {retrieval_time:.2f}ms, got {len(retrieval_results)} results")
        metrics.retrieval_latency.observe(retrieval_time / 1000)
        metrics.retrieval_results.set(len(retrieval_results))
        
        # Step 3: 重排序
        final_results = retrieval_results
        if rerank and len(retrieval_results) > 0:
            rerank_start = time.time()
            final_results = await self.reranker.rerank(
                query=query,
                candidates=retrieval_results,
                top_k=top_k
            )
            rerank_time = (time.time() - rerank_start) * 1000
            logger.info(f"Reranking completed in {rerank_time:.2f}ms")
            metrics.rerank_latency.observe(rerank_time / 1000)
        
        # Step 4: 生成答案
        if len(final_results) == 0:
            return {
                "query": query,
                "answer": "抱歉，未找到相关信息。",
                "sources": [],
                "rewritten_queries": rewritten_queries,
                "latency_ms": (time.time() - start_time) * 1000
            }
        
        generate_start = time.time()
        answer = await self.generator.generate(
            query=query,
            contexts=final_results,
            conversation_id=conversation_id
        )
        generate_time = (time.time() - generate_start) * 1000
        logger.info(f"Generation completed in {generate_time:.2f}ms")
        metrics.generation_latency.observe(generate_time / 1000)
        
        total_time = (time.time() - start_time) * 1000
        logger.info(f"Total query processing time: {total_time:.2f}ms")
        
        return {
            "query": query,
            "answer": answer,
            "sources": [
                {
                    "id": r.get("id", ""),
                    "content": r.get("content", ""),
                    "score": r.get("score", 0),
                    "metadata": r.get("metadata", {})
                }
                for r in final_results
            ],
            "rewritten_queries": rewritten_queries,
            "latency_ms": total_time
        }
    
    async def retrieve(
        self,
        query: str,
        top_k: int = 10,
        rewrite: bool = True,
        rerank: bool = True
    ) -> List[Dict[str, Any]]:
        """仅检索，不生成"""
        rewritten_queries = []
        if rewrite:
            rewritten_queries = await self.rewriter.rewrite(query)
        else:
            rewritten_queries = [query]
        
        results = await self.retriever.retrieve(
            queries=rewritten_queries,
            top_k=top_k
        )
        
        if rerank and len(results) > 0:
            results = await self.reranker.rerank(query, results, top_k)
        
        return results
