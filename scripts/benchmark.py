#!/usr/bin/env python3
"""
RAG基准测试 - 效果闭环

在真实数据集(CMRC2018)上评估系统效果，记录：
- Recall@K
- MRR (Mean Reciprocal Rank)
- NDCG@K
- 平均响应时间

使用:
    python scripts/benchmark.py --dataset cmrc2018 --output results.json
"""
import argparse
import json
import time
import sys
from pathlib import Path
from typing import List, Dict, Any, Set
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rag.pipeline import DefaultRAGPipeline, RAGConfig
from evaluation.metrics import RetrievalEvaluator


# ========== CMRC2018 模拟数据 ==========
# 实际使用时替换为真实CMRC2018数据加载
CMRC2018_SAMPLE = [
    {
        "question": "什么是RAG技术？",
        "answer": "检索增强生成（RAG）是一种将检索技术与生成模型结合的方法。",
        "context": "检索增强生成（Retrieval-Augmented Generation, RAG）是一种将检索技术与生成模型结合的方法。它通过从外部知识库中检索相关信息，并将其作为上下文提供给语言模型，从而生成更准确、更可靠的回答。",
        "doc_id": "doc_rag_intro"
    },
    {
        "question": "RAG的核心优势是什么？",
        "answer": "减少幻觉、知识可更新、可解释性强、成本效益高。",
        "context": "RAG的核心优势包括：1. 减少幻觉：通过引用真实文档，降低模型编造信息的概率；2. 知识更新：无需重新训练模型，只需更新知识库即可注入新知识；3. 可解释性：回答可追溯到具体的文档来源；4. 成本效益：相比微调大模型，RAG的实施成本更低。",
        "doc_id": "doc_rag_advantages"
    },
    {
        "question": "RAG系统包含哪些核心模块？",
        "answer": "文档解析、文本分块、向量化、向量存储、检索、生成。",
        "context": "RAG系统通常包含以下核心模块：文档解析模块负责处理不同格式的文档；文本分块模块将长文档切分为合适大小的片段；向量化模块将文本转换为向量表示；向量存储模块高效存储和检索向量；检索模块根据查询找到相关文档；生成模块结合检索结果生成答案。",
        "doc_id": "doc_rag_modules"
    },
    {
        "question": "什么是向量检索？",
        "answer": "向量检索是通过计算向量相似度来找到相关文档的技术。",
        "context": "向量检索是一种通过计算查询向量与文档向量之间的相似度来找到相关文档的技术。常用的相似度度量包括余弦相似度、欧氏距离等。向量检索的优势在于能够捕捉语义相似性，即使关键词不完全匹配也能找到相关内容。",
        "doc_id": "doc_vector_search"
    },
    {
        "question": "文本分块的策略有哪些？",
        "answer": "固定长度分块、句子分块、语义分块、父子分块。",
        "context": "常见的文本分块策略包括：固定长度分块按固定字符数切分；句子分块按句子边界切分；语义分块根据语义完整性切分；父子分块同时维护大块和小块，兼顾精度和上下文。选择合适的分块策略对检索效果至关重要。",
        "doc_id": "doc_chunking"
    },
    {
        "question": "如何评估RAG系统的效果？",
        "answer": "通过检索指标和生成指标综合评估。",
        "context": "RAG系统的效果评估包括检索质量指标（如Recall@K、Precision@K、MRR、NDCG）和生成质量指标（如忠实度、答案相关性、幻觉检测）。端到端评估还需要考虑延迟、吞吐量等性能指标。",
        "doc_id": "doc_evaluation"
    },
    {
        "question": "Embedding模型如何选择？",
        "answer": "根据语言、领域、精度要求选择。",
        "context": "选择Embedding模型时需要考虑：语言适配性（中文推荐BGE、M3E）、领域相关性（通用领域 vs 垂直领域）、精度与效率的权衡、模型大小与部署成本。BAAI的BGE系列是中文场景的首选。",
        "doc_id": "doc_embedding"
    },
    {
        "question": "什么是查询改写？",
        "answer": "通过改写原始查询来提升检索效果的技术。",
        "context": "查询改写（Query Rewriting）是通过改写原始查询来提升检索效果的技术。常见方法包括：多查询扩展（Multi-Query）、假设文档嵌入（HyDE）、查询扩展（Query Expansion）。改写后的查询能够覆盖更多相关文档。",
        "doc_id": "doc_query_rewrite"
    },
    {
        "question": "混合检索是什么？",
        "answer": "结合向量检索和关键词检索的方法。",
        "context": "混合检索（Hybrid Retrieval）是结合向量检索和关键词检索的方法。向量检索捕捉语义相似性，关键词检索保证精确匹配。通过RRF（Reciprocal Rank Fusion）等算法融合两者的结果，能够兼顾召回率和准确率。",
        "doc_id": "doc_hybrid_search"
    },
    {
        "question": "RAG如何应对长文档？",
        "answer": "通过分块、摘要、层级检索等方法处理。",
        "context": "处理长文档的RAG策略包括：智能分块保留上下文、文档摘要提取关键信息、层级检索先定位章节再查找细节、父文档检索返回完整上下文。这些方法能够在保持精度的同时处理大量内容。",
        "doc_id": "doc_long_docs"
    }
]


def load_dataset(dataset_name: str = "cmrc2018") -> tuple:
    """
    加载评估数据集
    
    Returns:
        documents: 文档列表 (text, doc_id)
        qa_pairs: 问答对列表 (question, answer, doc_id)
    """
    # 从模拟数据构建文档库
    documents = []
    for item in CMRC2018_SAMPLE:
        documents.append({
            "id": item["doc_id"],
            "text": item["context"]
        })
    
    # 构建问答对
    qa_pairs = []
    for item in CMRC2018_SAMPLE:
        qa_pairs.append({
            "question": item["question"],
            "answer": item["answer"],
            "doc_id": item["doc_id"]
        })
    
    print(f"📚 加载数据集: {dataset_name}")
    print(f"   文档数: {len(documents)}")
    print(f"   问答对: {len(qa_pairs)}")
    
    return documents, qa_pairs


def run_benchmark(
    documents: List[Dict],
    qa_pairs: List[Dict],
    config: RAGConfig = None
) -> Dict[str, Any]:
    """
    运行基准测试
    
    评估流程:
    1. 文档入库
    2. 对每个问题进行检索
    3. 计算检索指标
    4. 记录响应时间
    """
    print("\n" + "="*60)
    print("开始基准测试")
    print("="*60)
    
    # 初始化Pipeline
    if config is None:
        config = RAGConfig(
            chunk_size=500,
            chunk_overlap=50,
            top_k=10,
            enable_query_rewrite=False  # 基础版本，暂不开启改写
        )
    
    pipeline = DefaultRAGPipeline(config)
    
    # Step 1: 文档入库
    print("\n[1/3] 文档入库...")
    # 创建临时文档文件
    import tempfile
    doc_paths = []
    for doc in documents:
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.txt', delete=False, encoding='utf-8'
        ) as f:
            f.write(doc["text"])
            doc_paths.append((f.name, doc["id"]))
    
    # 入库
    for path, doc_id in doc_paths:
        result = pipeline.ingest_document(path)
        if not result.success:
            print(f"   ⚠️ 入库失败: {doc_id}")
    
    # 清理临时文件
    import os
    for path, _ in doc_paths:
        os.unlink(path)
    
    print(f"   ✓ 入库完成，向量库文档数: {pipeline._vector_store.count()}")
    
    # Step 2: 检索测试
    print("\n[2/3] 检索测试...")
    
    queries = []
    retrieved_results = []
    ground_truth = []
    latencies = []
    
    for idx, qa in enumerate(qa_pairs, 1):
        query = qa["question"]
        truth = {qa["doc_id"]}
        
        # 记录检索时间
        start_time = time.time()
        result = pipeline.query(query, use_rewrite=False)
        latency = (time.time() - start_time) * 1000  # ms
        
        queries.append(query)
        retrieved_results.append(result.retrieved_docs)
        ground_truth.append(truth)
        latencies.append(latency)
        
        if idx <= 3:  # 只显示前3个示例
            print(f"   [{idx}] {query[:30]}...")
            print(f"       检索到: {len(result.retrieved_docs)}个，耗时: {latency:.1f}ms")
    
    print(f"   ✓ 完成 {len(qa_pairs)} 个查询")
    
    # Step 3: 计算指标
    print("\n[3/3] 计算评估指标...")
    
    evaluator = RetrievalEvaluator()
    metrics = evaluator.evaluate(queries, retrieved_results, ground_truth)
    
    # 汇总结果
    results = {
        "config": {
            "chunk_size": config.chunk_size,
            "chunk_overlap": config.chunk_overlap,
            "top_k": config.top_k,
            "embedding_model": config.embedding_model
        },
        "dataset": {
            "name": "cmrc2018_sample",
            "num_documents": len(documents),
            "num_queries": len(qa_pairs)
        },
        "retrieval_metrics": {
            "recall_at_1": round(metrics.recall_at_k[1], 4),
            "recall_at_3": round(metrics.recall_at_k[3], 4),
            "recall_at_5": round(metrics.recall_at_k[5], 4),
            "recall_at_10": round(metrics.recall_at_k[10], 4),
            "precision_at_1": round(metrics.precision_at_k[1], 4),
            "precision_at_3": round(metrics.precision_at_k[3], 4),
            "precision_at_5": round(metrics.precision_at_k[5], 4),
            "ndcg_at_3": round(metrics.ndcg_at_k[3], 4),
            "ndcg_at_5": round(metrics.ndcg_at_k[5], 4),
            "mrr": round(metrics.mrr, 4),
            "map": round(metrics.map_score, 4)
        },
        "performance": {
            "avg_latency_ms": round(sum(latencies) / len(latencies), 2),
            "min_latency_ms": round(min(latencies), 2),
            "max_latency_ms": round(max(latencies), 2),
            "p95_latency_ms": round(sorted(latencies)[int(len(latencies)*0.95)], 2)
        },
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    
    return results


def print_results(results: Dict[str, Any]):
    """打印测试结果"""
    print("\n" + "="*60)
    print("📊 基准测试结果")
    print("="*60)
    
    print(f"\n配置参数:")
    for key, value in results["config"].items():
        print(f"   {key}: {value}")
    
    print(f"\n数据集:")
    print(f"   名称: {results['dataset']['name']}")
    print(f"   文档数: {results['dataset']['num_documents']}")
    print(f"   查询数: {results['dataset']['num_queries']}")
    
    print(f"\n检索指标:")
    metrics = results["retrieval_metrics"]
    print(f"   Recall@1:    {metrics['recall_at_1']:.2%}")
    print(f"   Recall@3:    {metrics['recall_at_3']:.2%}")
    print(f"   Recall@5:    {metrics['recall_at_5']:.2%}")
    print(f"   Recall@10:   {metrics['recall_at_10']:.2%}")
    print(f"   Precision@1: {metrics['precision_at_1']:.2%}")
    print(f"   Precision@5: {metrics['precision_at_5']:.2%}")
    print(f"   MRR:         {metrics['mrr']:.4f}")
    print(f"   MAP:         {metrics['map']:.4f}")
    
    print(f"\n性能指标:")
    perf = results["performance"]
    print(f"   平均延迟: {perf['avg_latency_ms']:.1f}ms")
    print(f"   P95延迟:  {perf['p95_latency_ms']:.1f}ms")
    print(f"   最小延迟: {perf['min_latency_ms']:.1f}ms")
    print(f"   最大延迟: {perf['max_latency_ms']:.1f}ms")
    
    print("\n" + "="*60)


def main():
    parser = argparse.ArgumentParser(description="RAG基准测试")
    parser.add_argument("--dataset", default="cmrc2018", help="数据集名称")
    parser.add_argument("--output", default="benchmark_results.json", help="输出文件")
    parser.add_argument("--chunk-size", type=int, default=500, help="分块大小")
    parser.add_argument("--top-k", type=int, default=10, help="检索数量")
    
    args = parser.parse_args()
    
    # 加载数据
    documents, qa_pairs = load_dataset(args.dataset)
    
    # 配置
    config = RAGConfig(
        chunk_size=args.chunk_size,
        top_k=args.top_k
    )
    
    # 运行测试
    results = run_benchmark(documents, qa_pairs, config)
    
    # 打印结果
    print_results(results)
    
    # 保存结果
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ 结果已保存: {args.output}")


if __name__ == "__main__":
    main()

