"""
RAG Engine - 核心RAG引擎
整合查询改写、多路检索、重排序、生成的完整流程
"""
import time
from typing import Any, Dict, List, Optional

from src.core.config import settings
from src.core.execution_trace import ExecutionTrace, StageTrace
from src.core.logging import get_logger
from src.core.monitoring import metrics
from src.core.query_router import LightweightQueryRouter
from src.core.retrieval_filters import RetrievalAccessContext, RetrievalFilterEngine
from src.generation.generator import LLMGenerator
from src.rerank.three_stage import ThreeStageReranker
from src.retrieval.hybrid import HybridRetriever
from src.retrieval.rewrite import QueryRewriter

logger = get_logger(__name__)


class RAGEngine:
    """企业级RAG引擎"""

    def __init__(self):
        logger.info("Initializing RAG Engine...")

        self.router = LightweightQueryRouter()
        logger.info("✓ Query router initialized")

        self.rewriter = QueryRewriter()
        logger.info("✓ Query rewriter initialized")

        self.retriever = HybridRetriever()
        logger.info("✓ Hybrid retriever initialized")

        self.reranker = ThreeStageReranker()
        logger.info("✓ Three-stage reranker initialized")

        self.generator = LLMGenerator()
        logger.info("✓ LLM generator initialized")

        self.filter_engine = RetrievalFilterEngine()
        logger.info("✓ Retrieval filter engine initialized")

        logger.info("RAG Engine initialized successfully")

    def _normalize_results(self, results: List[Any]) -> List[Dict[str, Any]]:
        normalized = []
        for item in results:
            if isinstance(item, dict):
                normalized.append(item)
                continue
            normalized.append(
                {
                    "id": getattr(item, "id", ""),
                    "content": getattr(item, "content", ""),
                    "score": getattr(item, "score", 0),
                    "metadata": getattr(item, "metadata", {}) or {},
                    "source": getattr(item, "source", "unknown"),
                }
            )
        return normalized

    def _deduplicate_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        deduped: List[Dict[str, Any]] = []
        seen_ids = set()
        seen_content = set()

        for item in results:
            doc_id = item.get("id") or item.get("metadata", {}).get("path") or item.get("metadata", {}).get("source")
            if doc_id:
                if doc_id in seen_ids:
                    continue
                seen_ids.add(doc_id)
            else:
                content_key = (item.get("content", "") or "")[:200]
                if content_key in seen_content:
                    continue
                seen_content.add(content_key)
            deduped.append(item)

        return deduped

    async def query(
        self,
        query: str,
        conversation_id: Optional[str] = None,
        top_k: int = 5,
        rewrite: bool = True,
        rerank: bool = True,
        trace_id: Optional[str] = None,
        access_context: Optional[RetrievalAccessContext] = None,
    ) -> Dict[str, Any]:
        start_time = time.time()
        logger.info(f"Processing query: {query}")

        route_decision = self.router.route(query)
        metrics.record_route(route_decision.task_type, route_decision.route)
        effective_rewrite = rewrite and route_decision.rewrite_enabled
        effective_rerank = rerank and route_decision.rerank_enabled
        generation_top_k = min(max(top_k, 1), route_decision.recommended_top_k)
        retrieval_top_k = max(settings.RETRIEVAL_TOP_K, generation_top_k)
        execution_trace = ExecutionTrace(
            trace_id=trace_id or f"trace_{int(start_time * 1000)}",
            route=route_decision.to_dict(),
            notes=[],
        )
        if route_decision.tool_candidate:
            execution_trace.notes.append(
                "Current pipeline remains retrieval-oriented; tool/workflow execution is marked as future harness expansion."
            )

        rewrite_stage = StageTrace(stage="route_and_rewrite", started_at_ms=time.time() * 1000)
        execution_trace.add_stage(rewrite_stage)
        if effective_rewrite:
            rewritten_queries = await self.rewriter.rewrite(query, conversation_id=conversation_id)
            logger.info(f"Generated {len(rewritten_queries)} rewritten queries")
        else:
            rewritten_queries = [query]
        rewrite_stage.finish(
            query_length=len(query),
            rewrite_enabled=effective_rewrite,
            rewritten_queries=rewritten_queries[:5],
            task_type=route_decision.task_type,
            route=route_decision.route,
        )

        retrieval_stage = StageTrace(stage="retrieve", started_at_ms=time.time() * 1000)
        execution_trace.add_stage(retrieval_stage)
        retrieval_start = time.time()

        retrieval_results = []
        for rewritten_query in rewritten_queries:
            per_query_results = await self.retriever.retrieve(
                query=rewritten_query,
                top_k=retrieval_top_k,
            )
            retrieval_results.extend(self._normalize_results(per_query_results))

        filtered_results = self.filter_engine.filter_results(retrieval_results, access_context)
        deduped_results = self._deduplicate_results(filtered_results)
        retrieval_time = (time.time() - retrieval_start) * 1000
        logger.info(f"Retrieval completed in {retrieval_time:.2f}ms, got {len(deduped_results)} deduped results")
        metrics.retrieval_latency.observe(retrieval_time / 1000)
        metrics.retrieval_results.set(len(deduped_results))
        retrieval_stage.finish(
            results_count=len(deduped_results),
            raw_results_count=len(retrieval_results),
            filtered_results_count=len(filtered_results),
            queries=rewritten_queries[:5],
            access_context=access_context.to_dict() if access_context else {},
            retrieval_top_k=retrieval_top_k,
            generation_top_k=generation_top_k,
        )

        final_results = deduped_results
        rerank_stage = StageTrace(stage="rerank", started_at_ms=time.time() * 1000)
        execution_trace.add_stage(rerank_stage)
        if effective_rerank and len(deduped_results) > 0:
            rerank_start = time.time()
            final_results = await self.reranker.rerank(
                query=query,
                candidates=deduped_results,
                top_k=retrieval_top_k,
                apply_generation_optimization=False,
            )
            final_results = self._deduplicate_results(self._normalize_results(final_results))
            rerank_time = (time.time() - rerank_start) * 1000
            logger.info(f"Reranking completed in {rerank_time:.2f}ms")
            metrics.rerank_latency.observe(rerank_time / 1000)
            rerank_stage.finish(enabled=True, before=len(deduped_results), after=len(final_results))
        else:
            rerank_stage.finish(enabled=False, before=len(deduped_results), after=len(final_results))

        if len(final_results) == 0:
            metrics.record_fallback("no_retrieval_results")
            metrics.record_support_confidence(0.0)
            execution_trace.fallback_triggered = True
            execution_trace.notes.append("No retrieval evidence found; returned abstain-style fallback.")
            return {
                "query": query,
                "answer": "抱歉，未找到足够的相关信息，当前不建议直接生成结论。",
                "sources": [],
                "rewritten_queries": rewritten_queries,
                "latency_ms": (time.time() - start_time) * 1000,
                "route": route_decision.to_dict(),
                "trace": execution_trace.to_dict(),
                "support": {
                    "has_support": False,
                    "confidence": 0.0,
                    "reason": "no_retrieval_results",
                    "citations_count": 0,
                },
            }

        generation_inputs = final_results[:generation_top_k]
        generation_stage = StageTrace(stage="generate", started_at_ms=time.time() * 1000)
        execution_trace.add_stage(generation_stage)
        generate_start = time.time()
        answer = await self.generator.generate(
            query=query,
            contexts=generation_inputs,
            conversation_id=conversation_id
        )
        generate_time = (time.time() - generate_start) * 1000
        logger.info(f"Generation completed in {generate_time:.2f}ms")
        metrics.generation_latency.observe(generate_time / 1000)
        generation_stage.finish(context_count=len(generation_inputs))

        total_time = (time.time() - start_time) * 1000
        logger.info(f"Total query processing time: {total_time:.2f}ms")

        support_confidence = round(min(1.0, 0.35 + 0.1 * min(len(generation_inputs), 5)), 2)
        support = {
            "has_support": len(generation_inputs) > 0,
            "confidence": support_confidence,
            "reason": "retrieval_backed_generation",
            "citations_count": len(generation_inputs),
        }
        metrics.record_support_confidence(support_confidence)

        return {
            "query": query,
            "answer": answer,
            "sources": final_results,
            "rewritten_queries": rewritten_queries,
            "latency_ms": total_time,
            "route": route_decision.to_dict(),
            "trace": execution_trace.to_dict(),
            "support": support,
        }

    async def retrieve(
        self,
        query: str,
        top_k: int = 10,
        rewrite: bool = True,
        rerank: bool = True,
        access_context: Optional[RetrievalAccessContext] = None,
    ) -> List[Dict[str, Any]]:
        route_decision = self.router.route(query)
        metrics.record_route(route_decision.task_type, route_decision.route)
        effective_rewrite = rewrite and route_decision.rewrite_enabled
        effective_rerank = rerank and route_decision.rerank_enabled
        effective_top_k = max(top_k, route_decision.recommended_top_k)

        if effective_rewrite:
            rewritten_queries = await self.rewriter.rewrite(query)
        else:
            rewritten_queries = [query]

        results = []
        for rewritten_query in rewritten_queries:
            per_query_results = await self.retriever.retrieve(query=rewritten_query, top_k=effective_top_k)
            results.extend(self._normalize_results(per_query_results))

        results = self.filter_engine.filter_results(results, access_context)
        results = self._deduplicate_results(results)

        if effective_rerank and len(results) > 0:
            results = await self.reranker.rerank(
                query,
                results,
                effective_top_k,
                apply_generation_optimization=False,
            )
            results = self._deduplicate_results(self._normalize_results(results))

        return results[:effective_top_k]
