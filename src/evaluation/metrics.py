"""
RAG Evaluation Metrics - RAG评估指标
支持检索质量、生成质量、端到端效果评估
"""
from collections import defaultdict
from dataclasses import dataclass
import math
import re
from typing import Any, Dict, List, Set

from src.core.monitoring import metrics

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False
    np = None


@dataclass
class RetrievalMetrics:
    recall_at_k: Dict[int, float]
    precision_at_k: Dict[int, float]
    ndcg_at_k: Dict[int, float]
    mrr: float
    map_score: float


@dataclass
class GenerationMetrics:
    faithfulness: float
    answer_relevance: float
    context_relevance: float
    hallucination_score: float


@dataclass
class EndToEndMetrics:
    latency_ms: float
    throughput_qps: float
    cost_per_query: float
    user_satisfaction: float


class RetrievalEvaluator:
    def __init__(self):
        self.k_values = [1, 3, 5, 10, 20]

    def evaluate(
        self,
        queries: List[str],
        retrieved_results: List[List[Dict[str, Any]]],
        ground_truth: List[Set[str]]
    ) -> RetrievalMetrics:
        recall_at_k = defaultdict(list)
        precision_at_k = defaultdict(list)
        ndcg_at_k = defaultdict(list)
        reciprocal_ranks = []
        average_precisions = []

        for _query, results, relevant in zip(queries, retrieved_results, ground_truth):
            retrieved_ids = [r["id"] for r in results]
            deduped_retrieved_ids = []
            seen_ids = set()
            for doc_id in retrieved_ids:
                if doc_id in seen_ids:
                    continue
                seen_ids.add(doc_id)
                deduped_retrieved_ids.append(doc_id)

            for k in self.k_values:
                top_k = set(deduped_retrieved_ids[:k])
                recall = len(top_k & relevant) / len(relevant) if relevant else 0.0
                recall_at_k[k].append(recall)
                precision = len(top_k & relevant) / k if k > 0 else 0.0
                precision_at_k[k].append(precision)
                ndcg = self._compute_ndcg(deduped_retrieved_ids[:k], relevant)
                ndcg_at_k[k].append(ndcg)

            reciprocal_ranks.append(self._compute_mrr(deduped_retrieved_ids, relevant))
            average_precisions.append(self._compute_ap(deduped_retrieved_ids, relevant))

        def safe_mean(values):
            if not values:
                return 0.0
            if HAS_NUMPY:
                return float(np.mean(values))
            return sum(values) / len(values)

        return RetrievalMetrics(
            recall_at_k={k: safe_mean(v) for k, v in recall_at_k.items()},
            precision_at_k={k: safe_mean(v) for k, v in precision_at_k.items()},
            ndcg_at_k={k: safe_mean(v) for k, v in ndcg_at_k.items()},
            mrr=safe_mean(reciprocal_ranks),
            map_score=safe_mean(average_precisions)
        )

    def _compute_ndcg(self, retrieved: List[str], relevant: Set[str]) -> float:
        if not relevant:
            return 0.0

        def log2(x):
            if HAS_NUMPY:
                return np.log2(x)
            return math.log2(x)

        dcg = 0.0
        for i, doc_id in enumerate(retrieved):
            if doc_id in relevant:
                dcg += 1.0 / log2(i + 2)

        ideal_len = min(len(relevant), len(retrieved))
        idcg = sum(1.0 / log2(i + 2) for i in range(ideal_len))
        return dcg / idcg if idcg > 0 else 0.0

    def _compute_mrr(self, retrieved: List[str], relevant: Set[str]) -> float:
        for i, doc_id in enumerate(retrieved):
            if doc_id in relevant:
                return 1.0 / (i + 1)
        return 0.0

    def _compute_ap(self, retrieved: List[str], relevant: Set[str]) -> float:
        if not relevant:
            return 0.0

        num_relevant = 0
        precision_sum = 0.0
        for i, doc_id in enumerate(retrieved):
            if doc_id in relevant:
                num_relevant += 1
                precision_sum += num_relevant / (i + 1)
        return precision_sum / len(relevant) if relevant else 0.0


class GenerationEvaluator:
    def __init__(self, nli_model=None):
        self.nli_model = nli_model

    def evaluate_faithfulness(self, answer: str, contexts: List[str]) -> float:
        claims = self._extract_claims(answer)
        if not claims:
            return 1.0

        supported = 0
        context_text = " ".join(contexts).lower()
        for claim in claims:
            claim_keywords = set(claim.lower().split())
            if any(kw in context_text for kw in claim_keywords):
                supported += 1
        return supported / len(claims)

    def evaluate_answer_relevance(self, query: str, answer: str) -> float:
        query_words = set(query.lower().split())
        answer_words = set(answer.lower().split())
        if not query_words:
            return 0.0
        return len(query_words & answer_words) / len(query_words)

    def detect_hallucination(self, answer: str, contexts: List[str]) -> float:
        answer_entities = self._extract_entities(answer)
        if not answer_entities:
            return 0.0
        context_entities = self._extract_entities(" ".join(contexts))
        hallucinated = answer_entities - context_entities
        return len(hallucinated) / len(answer_entities) if answer_entities else 0.0

    def _extract_claims(self, text: str) -> List[str]:
        sentences = re.split(r'[。！？.!?]', text)
        return [s.strip() for s in sentences if len(s.strip()) > 10]

    def _extract_entities(self, text: str) -> Set[str]:
        pattern = r'[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*'
        return set(re.findall(pattern, text))


class BenchmarkRunner:
    """基准测试运行器"""

    def __init__(self, rag_engine):
        self.rag_engine = rag_engine
        self.retrieval_evaluator = RetrievalEvaluator()
        self.generation_evaluator = GenerationEvaluator()

    @staticmethod
    def _safe_mean(values: List[float]) -> float:
        if not values:
            return 0.0
        if HAS_NUMPY:
            return float(np.mean(values))
        return sum(values) / len(values)

    @staticmethod
    def _safe_percentile(values: List[float], percentile: float) -> float:
        if not values:
            return 0.0
        sorted_values = sorted(values)
        if HAS_NUMPY:
            return float(np.percentile(sorted_values, percentile))
        if len(sorted_values) == 1:
            return sorted_values[0]
        position = (len(sorted_values) - 1) * (percentile / 100)
        lower = int(math.floor(position))
        upper = int(math.ceil(position))
        if lower == upper:
            return sorted_values[lower]
        weight = position - lower
        return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight

    async def run_benchmark(
        self,
        test_dataset: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        queries = [item["query"] for item in test_dataset]
        ground_truth = [set(item["relevant_docs"]) for item in test_dataset]

        metrics.record_evaluation_run(len(test_dataset))

        results = []
        latencies = []
        support_confidences = []
        fallback_count = 0

        for query in queries:
            import time
            start = time.time()
            result = await self.rag_engine.query(query)
            latency = (time.time() - start) * 1000

            results.append(result)
            latencies.append(latency)
            support_confidences.append(result.get("support", {}).get("confidence", 0.0))
            if not result.get("support", {}).get("has_support", False):
                fallback_count += 1

        retrieved_results = [[s for s in r["sources"]] for r in results]

        retrieval_metrics = self.retrieval_evaluator.evaluate(
            queries, retrieved_results, ground_truth
        )

        generation_metrics = []
        badcases = []
        for query, result in zip(queries, results):
            contexts = [s["content"] for s in result["sources"]]
            answer = result["answer"]

            faithfulness = self.generation_evaluator.evaluate_faithfulness(answer, contexts)
            relevance = self.generation_evaluator.evaluate_answer_relevance(query, answer)
            hallucination = self.generation_evaluator.detect_hallucination(answer, contexts)
            support = result.get("support", {})

            per_query = {
                "query": query,
                "faithfulness": faithfulness,
                "relevance": relevance,
                "hallucination": hallucination,
                "support_confidence": support.get("confidence", 0.0),
                "has_support": support.get("has_support", False),
                "sources_count": len(result.get("sources", [])),
            }
            generation_metrics.append(per_query)

            reasons = []
            if not per_query["has_support"]:
                reasons.append("fallback_or_no_support")
            if per_query["support_confidence"] < 0.5:
                reasons.append("low_support_confidence")
            if per_query["hallucination"] > 0.3:
                reasons.append("hallucination_risk")
            if per_query["faithfulness"] < 0.5:
                reasons.append("low_faithfulness")
            if reasons:
                badcases.append(
                    {
                        "query": query,
                        "reasons": reasons,
                        "support": support,
                        "route": result.get("route", {}),
                        "trace_id": result.get("trace", {}).get("trace_id"),
                        "sources_count": len(result.get("sources", [])),
                    }
                )

        warnings = []
        if len(queries) < 10:
            warnings.append("当前为轻量级验证数据集，结果仅用于方向性判断，不应用作最终对外指标。")
        if badcases:
            warnings.append("已输出 badcases 列表，建议优先检查 support 低或 fallback 触发的样本。")

        report = {
            "meta": {
                "validation_level": "lightweight",
                "dataset_size": len(queries),
                "warnings": warnings,
            },
            "retrieval": {
                "recall@20": retrieval_metrics.recall_at_k.get(20, 0),
                "precision@3": retrieval_metrics.precision_at_k.get(3, 0),
                "ndcg@10": retrieval_metrics.ndcg_at_k.get(10, 0),
                "mrr": retrieval_metrics.mrr,
                "map": retrieval_metrics.map_score,
            },
            "generation": {
                "avg_faithfulness": self._safe_mean([m["faithfulness"] for m in generation_metrics]),
                "avg_relevance": self._safe_mean([m["relevance"] for m in generation_metrics]),
                "avg_hallucination": self._safe_mean([m["hallucination"] for m in generation_metrics]),
            },
            "performance": {
                "avg_latency_ms": self._safe_mean(latencies),
                "p99_latency_ms": self._safe_percentile(latencies, 99),
                "p95_latency_ms": self._safe_percentile(latencies, 95),
                "avg_support_confidence": self._safe_mean(support_confidences),
                "fallback_rate": fallback_count / len(queries) if queries else 0.0,
            },
            "details": {
                "num_queries": len(queries),
                "generation_metrics_per_query": generation_metrics,
                "badcases": badcases,
            }
        }

        return report
