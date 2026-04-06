#!/usr/bin/env python3
"""
本地迭代实验脚本 - Local RAG Experiments
支持对比不同策略的效果，生成实验报告

使用方法:
    python scripts/run_experiments.py --experiment chunk_size
    python scripts/run_experiments.py --experiment embedding
    python scripts/run_experiments.py --experiment all
"""
import asyncio
import json
import time
import argparse
from pathlib import Path
from typing import List, Dict, Any
from dataclasses import asdict

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.evaluation.metrics import RetrievalEvaluator, RetrievalMetrics
from src.core.logging import get_logger

logger = get_logger(__name__)


# ============== 数据加载 ==============

def load_arxiv_qa_pairs(data_file: str = "data/qa_pairs.json") -> tuple:
    """
    加载Arxiv问答对数据
    
    如果真实数据不存在，返回模拟数据
    """
    data_path = Path(data_file)
    
    if data_path.exists():
        print(f"📚 加载真实数据: {data_file}")
        with open(data_path, 'r', encoding='utf-8') as f:
            qa_pairs = json.load(f)
        
        queries = [qa['question'] for qa in qa_pairs]
        # ground truth用paper_id表示相关文档
        ground_truth = [{qa.get('paper_id', '')} for qa in qa_pairs]
        
        print(f"✅ 加载了 {len(queries)} 个真实查询")
        return queries, ground_truth
    else:
        print("⚠️ 真实数据不存在，使用模拟数据")
        print("   提示: 运行 python scripts/download_arxiv.py 下载真实数据")
        return SAMPLE_QUERIES_MOCK, SAMPLE_GROUND_TRUTH_MOCK


# 模拟数据（备用）
SAMPLE_QUERIES_MOCK = [
    "什么是机器学习？",
    "深度学习和神经网络的关系",
    "Transformer架构的原理",
    "如何优化大模型推理速度",
    "RAG系统的评估指标",
    "向量数据库的选型",
    "LLM幻觉问题如何解决",
    "Prompt Engineering最佳实践",
    "Fine-tuning vs RAG",
    "多模态大模型的发展",
]

SAMPLE_GROUND_TRUTH_MOCK = [
    {"doc_ml_001", "doc_ml_005", "doc_ai_012"},
    {"doc_dl_001", "doc_nn_003", "doc_ai_008"},
    {"doc_transformer_001", "doc_nlp_005"},
    {"doc_opt_002", "doc_perf_007", "doc_llm_015"},
    {"doc_eval_001", "doc_rag_003"},
    {"doc_db_001", "doc_vec_004", "doc_milvus_002"},
    {"doc_hallucination_001", "doc_llm_009"},
    {"doc_prompt_001", "doc_prompt_005", "doc_prompt_012"},
    {"doc_ft_001", "doc_rag_007", "doc_llm_020"},
    {"doc_mm_001", "doc_vlm_003"},
]


class MockRetriever:
    """模拟检索器 - 用于本地实验"""
    
    def __init__(self, strategy: str, config: Dict[str, Any]):
        self.strategy = strategy
        self.config = config
        self.name = config.get("name", strategy)
    
    async def retrieve(self, query: str, top_k: int = 10) -> List[Dict[str, Any]]:
        """模拟检索，根据策略返回不同质量的结果"""
        await asyncio.sleep(0.01)  # 模拟延迟
        
        # 根据策略模拟不同的recall率
        base_quality = self._get_base_quality()
        
        # 模拟检索结果（包含一些相关的，一些不相关的）
        results = []
        for i in range(top_k):
            # 模拟相关性分数递减
            score = base_quality * (1 - i * 0.08) + (0.1 if i < 3 else 0)
            
            # 模拟文档ID
            doc_id = f"doc_{self.strategy}_{i:03d}"
            
            results.append({
                "id": doc_id,
                "content": f"Result {i} for query with {self.name}",
                "score": max(0.1, score),
                "strategy": self.strategy
            })
        
        return results
    
    def _get_base_quality(self) -> float:
        """根据配置返回模拟质量分数"""
        quality_map = {
            # Chunk策略
            "chunk_small": 0.65,
            "chunk_medium": 0.72,
            "chunk_large": 0.68,
            "chunk_parent_child": 0.81,
            
            # Embedding模型
            "emb_bge_small": 0.72,
            "emb_bge_base": 0.78,
            "emb_bge_large": 0.82,
            "emb_gte": 0.80,
            
            # 检索策略
            "dense_only": 0.75,
            "bm25_only": 0.62,
            "hybrid": 0.84,
            
            # 查询改写
            "no_rewrite": 0.78,
            "hyde": 0.85,
            "multi_query": 0.86,
        }
        return quality_map.get(self.strategy, 0.70)


# ============== 实验配置 ==============

EXPERIMENTS = {
    "chunk_size": {
        "name": "Chunk Size Impact",
        "description": "测试不同chunk size对检索效果的影响",
        "variants": [
            {"name": "small (200)", "strategy": "chunk_small", "config": {"size": 200}},
            {"name": "medium (500)", "strategy": "chunk_medium", "config": {"size": 500}},
            {"name": "large (1000)", "strategy": "chunk_large", "config": {"size": 1000}},
            {"name": "parent-child", "strategy": "chunk_parent_child", "config": {"parent": 1000, "child": 200}},
        ]
    },
    "embedding": {
        "name": "Embedding Model Comparison",
        "description": "对比不同embedding模型的效果",
        "variants": [
            {"name": "BGE-small", "strategy": "emb_bge_small", "config": {"model": "bge-small"}},
            {"name": "BGE-base", "strategy": "emb_bge_base", "config": {"model": "bge-base"}},
            {"name": "BGE-large", "strategy": "emb_bge_large", "config": {"model": "bge-large"}},
            {"name": "GTE-large", "strategy": "emb_gte", "config": {"model": "gte-large"}},
        ]
    },
    "retrieval": {
        "name": "Retrieval Strategy",
        "description": "对比不同检索策略的效果",
        "variants": [
            {"name": "Dense Only", "strategy": "dense_only", "config": {}},
            {"name": "BM25 Only", "strategy": "bm25_only", "config": {}},
            {"name": "Hybrid (RRF)", "strategy": "hybrid", "config": {}},
        ]
    },
    "rewrite": {
        "name": "Query Rewriting",
        "description": "测试查询改写的效果",
        "variants": [
            {"name": "No Rewrite", "strategy": "no_rewrite", "config": {}},
            {"name": "HyDE", "strategy": "hyde", "config": {}},
            {"name": "Multi-Query", "strategy": "multi_query", "config": {}},
        ]
    },
}


# ============== 实验运行器 ==============

class ExperimentRunner:
    """实验运行器"""
    
    def __init__(
        self,
        output_dir: str = "experiments",
        queries: List[str] = None,
        ground_truth: List[set] = None
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.evaluator = RetrievalEvaluator()
        self.queries = queries or SAMPLE_QUERIES_MOCK
        self.ground_truth = ground_truth or SAMPLE_GROUND_TRUTH_MOCK
    
    async def run_experiment(
        self,
        exp_key: str,
        exp_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """运行单个实验"""
        logger.info(f"\n{'='*60}")
        logger.info(f"Running Experiment: {exp_config['name']}")
        logger.info(f"Description: {exp_config['description']}")
        logger.info(f"Data: {len(self.queries)} queries")
        logger.info(f"{'='*60}\n")
        
        results = []
        
        for variant in exp_config["variants"]:
            variant_name = variant["name"]
            strategy = variant["strategy"]
            config = variant["config"]
            
            logger.info(f"Testing variant: {variant_name}")
            
            # 创建检索器
            retriever = MockRetriever(strategy, config)
            
            # 执行检索
            start_time = time.time()
            all_results = []
            
            for query in self.queries:
                results_list = await retriever.retrieve(query, top_k=10)
                all_results.append(results_list)
            
            elapsed = time.time() - start_time
            latency_ms = (elapsed / len(self.queries)) * 1000
            
            # 评估指标
            metrics = self.evaluator.evaluate(
                queries=self.queries,
                retrieved_results=all_results,
                ground_truth=self.ground_truth
            )
            
            # 记录结果
            result = {
                "variant": variant_name,
                "strategy": strategy,
                "config": config,
                "metrics": {
                    "recall@1": round(metrics.recall_at_k[1], 3),
                    "recall@5": round(metrics.recall_at_k[5], 3),
                    "recall@10": round(metrics.recall_at_k[10], 3),
                    "mrr": round(metrics.mrr, 3),
                    "ndcg@5": round(metrics.ndcg_at_k[5], 3),
                    "latency_ms": round(latency_ms, 1),
                }
            }
            results.append(result)
            
            logger.info(f"  Recall@5: {result['metrics']['recall@5']}")
            logger.info(f"  MRR: {result['metrics']['mrr']}")
            logger.info(f"  Latency: {result['metrics']['latency_ms']}ms\n")
        
        # 保存实验结果
        exp_result = {
            "experiment": exp_key,
            "name": exp_config["name"],
            "description": exp_config["description"],
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "results": results
        }
        
        output_file = self.output_dir / f"{exp_key}_{time.strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(exp_result, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Results saved to: {output_file}")
        
        return exp_result
    
    def print_summary(self, exp_result: Dict[str, Any]):
        """打印实验摘要"""
        print(f"\n{'='*70}")
        print(f"Experiment Summary: {exp_result['name']}")
        print(f"{'='*70}")
        
        # 表头
        print(f"{'Variant':<20} {'Recall@5':>10} {'MRR':>10} {'NDCG@5':>10} {'Latency':>10}")
        print("-" * 70)
        
        # 结果行
        for r in exp_result["results"]:
            m = r["metrics"]
            print(f"{r['variant']:<20} {m['recall@5']:>10.3f} {m['mrr']:>10.3f} {m['ndcg@5']:>10.3f} {m['latency_ms']:>9.1f}ms")
        
        # 最佳结果
        best = max(exp_result["results"], key=lambda x: x["metrics"]["recall@5"])
        print(f"\n🏆 Best: {best['variant']} (Recall@5={best['metrics']['recall@5']:.3f})")
        print(f"{'='*70}\n")


# ============== 主入口 ==============

async def main():
    parser = argparse.ArgumentParser(description="Run RAG Experiments")
    parser.add_argument(
        "--experiment",
        choices=list(EXPERIMENTS.keys()) + ["all"],
        default="all",
        help="Which experiment to run"
    )
    parser.add_argument(
        "--output-dir",
        default="experiments",
        help="Output directory for results"
    )
    parser.add_argument(
        "--data-file",
        default="data/qa_pairs.json",
        help="QA pairs data file for real evaluation"
    )
    parser.add_argument(
        "--use-mock",
        action="store_true",
        help="Use mock data even if real data exists"
    )
    
    args = parser.parse_args()
    
    # 加载数据
    if args.use_mock:
        queries, ground_truth = SAMPLE_QUERIES_MOCK, SAMPLE_GROUND_TRUTH_MOCK
        print("🎭 使用模拟数据")
    else:
        queries, ground_truth = load_arxiv_qa_pairs(args.data_file)
    
    runner = ExperimentRunner(
        output_dir=args.output_dir,
        queries=queries,
        ground_truth=ground_truth
    )
    
    if args.experiment == "all":
        for exp_key, exp_config in EXPERIMENTS.items():
            result = await runner.run_experiment(exp_key, exp_config)
            runner.print_summary(result)
    else:
        exp_config = EXPERIMENTS[args.experiment]
        result = await runner.run_experiment(args.experiment, exp_config)
        runner.print_summary(result)
    
    logger.info("All experiments completed!")


if __name__ == "__main__":
    asyncio.run(main())
