"""
RAG Evaluation Metrics - RAG评估指标
支持检索质量、生成质量、端到端效果评估
"""
import numpy as np
from typing import List, Dict, Any, Optional, Set, Tuple
from dataclasses import dataclass
from collections import defaultdict
import re


@dataclass
class RetrievalMetrics:
    """检索质量指标"""
    recall_at_k: Dict[int, float]  # Recall@K
    precision_at_k: Dict[int, float]  # Precision@K
    ndcg_at_k: Dict[int, float]  # NDCG@K
    mrr: float  # Mean Reciprocal Rank
    map_score: float  # Mean Average Precision


@dataclass
class GenerationMetrics:
    """生成质量指标"""
    faithfulness: float  # 忠实度（基于NLI）
    answer_relevance: float  # 答案相关性
    context_relevance: float  # 上下文相关性
    hallucination_score: float  # 幻觉分数


@dataclass
class EndToEndMetrics:
    """端到端指标"""
    latency_ms: float  # 延迟
    throughput_qps: float  # 吞吐量
    cost_per_query: float  # 单次查询成本
    user_satisfaction: float  # 用户满意度（如果有反馈）


class RetrievalEvaluator:
    """检索评估器"""
    
    def __init__(self):
        self.k_values = [1, 3, 5, 10, 20]
    
    def evaluate(
        self,
        queries: List[str],
        retrieved_results: List[List[Dict[str, Any]]],
        ground_truth: List[Set[str]]
    ) -> RetrievalMetrics:
        """
        评估检索效果
        
        Args:
            queries: 查询列表
            retrieved_results: 每个查询的检索结果列表
            ground_truth: 每个查询的相关文档ID集合
        """
        recall_at_k = defaultdict(list)
        precision_at_k = defaultdict(list)
        ndcg_at_k = defaultdict(list)
        reciprocal_ranks = []
        average_precisions = []
        
        for query, results, relevant in zip(queries, retrieved_results, ground_truth):
            retrieved_ids = [r["id"] for r in results]
            
            # Recall@K, Precision@K, NDCG@K
            for k in self.k_values:
                top_k = set(retrieved_ids[:k])
                
                # Recall@K
                if relevant:
                    recall = len(top_k & relevant) / len(relevant)
                else:
                    recall = 0.0
                recall_at_k[k].append(recall)
                
                # Precision@K
                precision = len(top_k & relevant) / k if k > 0 else 0.0
                precision_at_k[k].append(precision)
                
                # NDCG@K
                ndcg = self._compute_ndcg(retrieved_ids[:k], relevant)
                ndcg_at_k[k].append(ndcg)
            
            # MRR
            rr = self._compute_mrr(retrieved_ids, relevant)
            reciprocal_ranks.append(rr)
            
            # MAP
            ap = self._compute_ap(retrieved_ids, relevant)
            average_precisions.append(ap)
        
        return RetrievalMetrics(
            recall_at_k={k: np.mean(v) for k, v in recall_at_k.items()},
            precision_at_k={k: np.mean(v) for k, v in precision_at_k.items()},
            ndcg_at_k={k: np.mean(v) for k, v in ndcg_at_k.items()},
            mrr=np.mean(reciprocal_ranks),
            map_score=np.mean(average_precisions)
        )
    
    def _compute_ndcg(self, retrieved: List[str], relevant: Set[str]) -> float:
        """计算NDCG@K"""
        if not relevant:
            return 0.0
        
        # DCG
        dcg = 0.0
        for i, doc_id in enumerate(retrieved):
            if doc_id in relevant:
                dcg += 1.0 / np.log2(i + 2)  # +2 because i starts at 0
        
        # IDCG
        ideal_len = min(len(relevant), len(retrieved))
        idcg = sum(1.0 / np.log2(i + 2) for i in range(ideal_len))
        
        return dcg / idcg if idcg > 0 else 0.0
    
    def _compute_mrr(self, retrieved: List[str], relevant: Set[str]) -> float:
        """计算MRR"""
        for i, doc_id in enumerate(retrieved):
            if doc_id in relevant:
                return 1.0 / (i + 1)
        return 0.0
    
    def _compute_ap(self, retrieved: List[str], relevant: Set[str]) -> float:
        """计算AP"""
        if not relevant:
            return 0.0
        
        num_relevant = 0
        precision_sum = 0.0
        
        for i, doc_id in enumerate(retrieved):
            if doc_id in relevant:
                num_relevant += 1
                precision_at_i = num_relevant / (i + 1)
                precision_sum += precision_at_i
        
        return precision_sum / len(relevant) if relevant else 0.0


class GenerationEvaluator:
    """生成质量评估器"""
    
    def __init__(self, nli_model=None):
        """
        Args:
            nli_model: 自然语言推理模型，用于评估忠实度
        """
        self.nli_model = nli_model
    
    def evaluate_faithfulness(
        self,
        answer: str,
        contexts: List[str]
    ) -> float:
        """
        评估忠实度（答案是否被上下文支持）
        
        方法：
        1. 从答案中提取声明
        2. 检查每个声明是否被上下文支持
        3. 计算被支持的声明比例
        """
        # 简化实现：基于关键词匹配
        # 实际生产环境应使用NLI模型
        claims = self._extract_claims(answer)
        
        if not claims:
            return 1.0  # 无声明，默认为忠实
        
        supported = 0
        context_text = " ".join(contexts).lower()
        
        for claim in claims:
            # 检查声明关键词是否在上下文中
            claim_keywords = set(claim.lower().split())
            if any(kw in context_text for kw in claim_keywords):
                supported += 1
        
        return supported / len(claims)
    
    def evaluate_answer_relevance(
        self,
        query: str,
        answer: str
    ) -> float:
        """评估答案与问题的相关性"""
        # 简化的相关性评估
        query_words = set(query.lower().split())
        answer_words = set(answer.lower().split())
        
        if not query_words:
            return 0.0
        
        overlap = len(query_words & answer_words)
        return overlap / len(query_words)
    
    def detect_hallucination(
        self,
        answer: str,
        contexts: List[str]
    ) -> float:
        """
        检测幻觉（答案中包含上下文未提及的信息）
        
        Returns:
            幻觉分数 (0-1)，越高表示幻觉越严重
        """
        # 提取答案中的命名实体
        answer_entities = self._extract_entities(answer)
        
        if not answer_entities:
            return 0.0
        
        context_text = " ".join(contexts)
        context_entities = self._extract_entities(context_text)
        
        # 计算答案中但不在上下文中的实体比例
        hallucinated = answer_entities - context_entities
        
        return len(hallucinated) / len(answer_entities) if answer_entities else 0.0
    
    def _extract_claims(self, text: str) -> List[str]:
        """从文本中提取声明/主张"""
        # 简化实现：按句号分割
        sentences = re.split(r'[。！？.!?]', text)
        return [s.strip() for s in sentences if len(s.strip()) > 10]
    
    def _extract_entities(self, text: str) -> Set[str]:
        """提取命名实体"""
        # 简化实现：提取大写字母开头的词组
        pattern = r'[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*'
        return set(re.findall(pattern, text))


class BenchmarkRunner:
    """基准测试运行器"""
    
    def __init__(self, rag_engine):
        self.rag_engine = rag_engine
        self.retrieval_evaluator = RetrievalEvaluator()
        self.generation_evaluator = GenerationEvaluator()
    
    async def run_benchmark(
        self,
        test_dataset: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        运行完整基准测试
        
        Args:
            test_dataset: 测试数据集，每项包含query和ground_truth
        """
        queries = [item["query"] for item in test_dataset]
        ground_truth = [set(item["relevant_docs"]) for item in test_dataset]
        
        # 执行查询
        results = []
        latencies = []
        
        for query in queries:
            import time
            start = time.time()
            result = await self.rag_engine.query(query)
            latency = (time.time() - start) * 1000
            
            results.append(result)
            latencies.append(latency)
        
        # 提取检索结果
        retrieved_results = [
            [s for s in r["sources"]] for r in results
        ]
        
        # 评估检索质量
        retrieval_metrics = self.retrieval_evaluator.evaluate(
            queries, retrieved_results, ground_truth
        )
        
        # 评估生成质量
        generation_metrics = []
        for query, result in zip(queries, results):
            contexts = [s["content"] for s in result["sources"]]
            answer = result["answer"]
            
            faithfulness = self.generation_evaluator.evaluate_faithfulness(
                answer, contexts
            )
            relevance = self.generation_evaluator.evaluate_answer_relevance(
                query, answer
            )
            hallucination = self.generation_evaluator.detect_hallucination(
                answer, contexts
            )
            
            generation_metrics.append({
                "faithfulness": faithfulness,
                "relevance": relevance,
                "hallucination": hallucination
            })
        
        # 汇总结果
        report = {
            "retrieval": {
                "recall@20": retrieval_metrics.recall_at_k.get(20, 0),
                "precision@3": retrieval_metrics.precision_at_k.get(3, 0),
                "ndcg@10": retrieval_metrics.ndcg_at_k.get(10, 0),
                "mrr": retrieval_metrics.mrr,
                "map": retrieval_metrics.map_score,
            },
            "generation": {
                "avg_faithfulness": np.mean([m["faithfulness"] for m in generation_metrics]),
                "avg_relevance": np.mean([m["relevance"] for m in generation_metrics]),
                "avg_hallucination": np.mean([m["hallucination"] for m in generation_metrics]),
            },
            "performance": {
                "avg_latency_ms": np.mean(latencies),
                "p99_latency_ms": np.percentile(latencies, 99),
                "p95_latency_ms": np.percentile(latencies, 95),
            },
            "details": {
                "num_queries": len(queries),
                "generation_metrics_per_query": generation_metrics,
            }
        }
        
        return report
