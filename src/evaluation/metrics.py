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

    @staticmethod
    def _dedup_source_ids(results: List[Dict[str, Any]]) -> List[str]:
        deduped = []
        seen = set()
        for item in results:
            doc_id = item.get("id")
            if not doc_id or doc_id in seen:
                continue
            seen.add(doc_id)
            deduped.append(doc_id)
        return deduped

    def _per_query_retrieval_detail(
        self,
        item: Dict[str, Any],
        result: Dict[str, Any],
        latency_ms: float,
    ) -> Dict[str, Any]:
        relevant_docs = set(item.get("relevant_docs", []))
        retrieved_ids = self._dedup_source_ids(result.get("sources", []))
        top3 = retrieved_ids[:3]
        top10 = retrieved_ids[:10]
        mrr = self.retrieval_evaluator._compute_mrr(retrieved_ids, relevant_docs)
        ap = self.retrieval_evaluator._compute_ap(retrieved_ids, relevant_docs)
        recall_at_20 = len(set(retrieved_ids[:20]) & relevant_docs) / len(relevant_docs) if relevant_docs else 0.0
        precision_at_3 = len(set(top3) & relevant_docs) / 3 if top3 else 0.0
        return {
            "id": item.get("id", ""),
            "query": item.get("query", ""),
            "category": item.get("category", "uncategorized"),
            "difficulty": item.get("difficulty", "unknown"),
            "relevant_docs": list(item.get("relevant_docs", [])),
            "retrieved_top3": top3,
            "retrieved_top10": top10,
            "top1": retrieved_ids[0] if retrieved_ids else None,
            "top1_hit": bool(retrieved_ids and retrieved_ids[0] in relevant_docs),
            "precision@3": precision_at_3,
            "recall@20": recall_at_20,
            "mrr": mrr,
            "ap": ap,
            "missed_relevant_docs": sorted(relevant_docs - set(retrieved_ids[:20])),
            "unexpected_top3": [doc_id for doc_id in top3 if doc_id not in relevant_docs],
            "latency_ms": latency_ms,
            "sources_count": len(result.get("sources", [])),
        }

    def _build_category_breakdown(
        self,
        per_query_retrieval: List[Dict[str, Any]],
        generation_metrics: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        by_category: Dict[str, Dict[str, List[float] | int]] = {}
        generation_by_query = {item["query"]: item for item in generation_metrics}

        for item in per_query_retrieval:
            category = item.get("category", "uncategorized")
            bucket = by_category.setdefault(
                category,
                {
                    "count": 0,
                    "precision@3": [],
                    "recall@20": [],
                    "mrr": [],
                    "ap": [],
                    "latency_ms": [],
                    "top1_hit": 0,
                    "faithfulness": [],
                    "relevance": [],
                    "hallucination": [],
                },
            )
            bucket["count"] += 1
            bucket["precision@3"].append(item["precision@3"])
            bucket["recall@20"].append(item["recall@20"])
            bucket["mrr"].append(item["mrr"])
            bucket["ap"].append(item["ap"])
            bucket["latency_ms"].append(item["latency_ms"])
            bucket["top1_hit"] += 1 if item["top1_hit"] else 0

            gen = generation_by_query.get(item["query"])
            if gen:
                bucket["faithfulness"].append(gen["faithfulness"])
                bucket["relevance"].append(gen["relevance"])
                bucket["hallucination"].append(gen["hallucination"])

        return {
            category: {
                "count": bucket["count"],
                "precision@3": self._safe_mean(bucket["precision@3"]),
                "recall@20": self._safe_mean(bucket["recall@20"]),
                "mrr": self._safe_mean(bucket["mrr"]),
                "map": self._safe_mean(bucket["ap"]),
                "avg_latency_ms": self._safe_mean(bucket["latency_ms"]),
                "top1_hit_rate": (bucket["top1_hit"] / bucket["count"]) if bucket["count"] else 0.0,
                "avg_faithfulness": self._safe_mean(bucket["faithfulness"]),
                "avg_relevance": self._safe_mean(bucket["relevance"]),
                "avg_hallucination": self._safe_mean(bucket["hallucination"]),
            }
            for category, bucket in by_category.items()
        }

    def _build_doc_dominance_stats(self, per_query_retrieval: List[Dict[str, Any]]) -> Dict[str, Any]:
        tracked_docs = ["README.md", "ARCHITECTURE.md"]
        total = len(per_query_retrieval)
        stats: Dict[str, Any] = {}

        for doc_id in tracked_docs:
            top1_count = sum(1 for item in per_query_retrieval if item.get("top1") == doc_id)
            top1_wrong = sum(
                1
                for item in per_query_retrieval
                if item.get("top1") == doc_id and doc_id not in set(item.get("relevant_docs", []))
            )
            top3_count = sum(1 for item in per_query_retrieval if doc_id in item.get("retrieved_top3", []))
            stats[doc_id] = {
                "top1_count": top1_count,
                "top1_rate": (top1_count / total) if total else 0.0,
                "wrong_top1_count": top1_wrong,
                "wrong_top1_rate": (top1_wrong / total) if total else 0.0,
                "top3_count": top3_count,
                "top3_rate": (top3_count / total) if total else 0.0,
            }

        return stats

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
        for item, result in zip(test_dataset, results):
            query = item["query"]
            contexts = [s["content"] for s in result["sources"]]
            answer = result["answer"]

            faithfulness = self.generation_evaluator.evaluate_faithfulness(answer, contexts)
            relevance = self.generation_evaluator.evaluate_answer_relevance(query, answer)
            hallucination = self.generation_evaluator.detect_hallucination(answer, contexts)
            support = result.get("support", {})

            per_query = {
                "id": item.get("id", ""),
                "query": query,
                "category": item.get("category", "uncategorized"),
                "difficulty": item.get("difficulty", "unknown"),
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
                        "id": item.get("id", ""),
                        "query": query,
                        "category": item.get("category", "uncategorized"),
                        "reasons": reasons,
                        "support": support,
                        "route": result.get("route", {}),
                        "trace_id": result.get("trace", {}).get("trace_id"),
                        "sources_count": len(result.get("sources", [])),
                    }
                )

        per_query_retrieval = [
            self._per_query_retrieval_detail(item, result, latency_ms)
            for item, result, latency_ms in zip(test_dataset, results, latencies)
        ]
        category_breakdown = self._build_category_breakdown(per_query_retrieval, generation_metrics)
        doc_dominance = self._build_doc_dominance_stats(per_query_retrieval)

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
                "per_query_retrieval": per_query_retrieval,
                "category_breakdown": category_breakdown,
                "doc_dominance": doc_dominance,
                "badcases": badcases,
            }
        }

        return report
