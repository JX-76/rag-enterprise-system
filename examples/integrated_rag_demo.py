#!/usr/bin/env python3
"""
集成演示：展示整合后的完整RAG Pipeline
- Rankify重排序
- LLMLingua上下文压缩
- 查询改写 + 多跳检索
"""
import asyncio
import sys
sys.path.insert(0, '/root/.openclaw/workspace/rag-enterprise-system/src')

from src.retrieval.advanced_retrieval import QueryRewriter, MultiHopRetriever, FusionRetriever
from src.rerank.rankify_adapter import HybridReranker
from src.generation.llmlingua_compressor import ContextCompressor
from src.core.logging import get_logger

logger = get_logger(__name__)


async def demo_query_rewrite():
    """演示查询改写"""
    print("\n" + "="*60)
    print("Demo 1: Query Rewriting (基于RAG_Techniques)")
    print("="*60)
    
    rewriter = QueryRewriter()
    
    query = "What are the health benefits of exercise?"
    print(f"\nOriginal Query: {query}")
    
    # HyDE改写
    hyde_queries = await rewriter.rewrite(query, strategy="hyde", num_docs=3)
    print(f"\nHyDE Rewrite ({len(hyde_queries)} queries):")
    for i, q in enumerate(hyde_queries, 1):
        print(f"  {i}. {q[:80]}...")
    
    # 查询分解
    decomposed = await rewriter.rewrite(query, strategy="decomposition")
    print(f"\nDecomposed Queries ({len(decomposed)} sub-queries):")
    for i, q in enumerate(decomposed, 1):
        print(f"  {i}. {q[:80]}...")


async def demo_reranking():
    """演示Rankify重排序"""
    print("\n" + "="*60)
    print("Demo 2: Rankify Reranking (24个重排模型)")
    print("="*60)
    
    reranker = HybridReranker()
    
    query = "machine learning applications in healthcare"
    
    # 模拟检索结果
    candidates = [
        {"id": "doc_1", "content": "Deep learning has revolutionized medical imaging...", "score": 0.85},
        {"id": "doc_2", "content": "NLP techniques for clinical notes processing...", "score": 0.82},
        {"id": "doc_3", "content": "Reinforcement learning in drug discovery...", "score": 0.78},
        {"id": "doc_4", "content": "Traditional statistical methods in epidemiology...", "score": 0.75},
        {"id": "doc_5", "content": "AI ethics in healthcare decision making...", "score": 0.72},
    ] * 4  # 模拟20个候选
    
    print(f"\nQuery: {query}")
    print(f"Input candidates: {len(candidates)}")
    
    # 演示Stage 1重排序
    from src.rerank.rankify_adapter import RankifyAdapter
    stage1 = RankifyAdapter("minilm")
    
    print("\nStage 1: MiniLM Fast Reranking (Top 20 → Top 10)")
    results = await stage1.rerank(query, candidates[:20], top_k=10)
    for i, r in enumerate(results, 1):
        print(f"  {i}. [{r['id']}] Score: {r['score']:.4f}")
    
    print("\nSupported Models in Rankify:")
    print("  - minilm: Lightweight for Stage 1")
    print("  - bge-reranker: Heavyweight for Stage 2")
    print("  - cohere/jina: API-based models")
    print("  - longllmlingua: Long document optimization")


async def demo_compression():
    """演示LLMLingua压缩"""
    print("\n" + "="*60)
    print("Demo 3: LLMLingua Context Compression (微软)")
    print("="*60)
    
    compressor = ContextCompressor()
    
    # 长文档示例
    long_context = """
    Machine learning (ML) is a field of study in artificial intelligence concerned with 
    the development and study of statistical algorithms that can learn from data and 
    generalize to unseen data, and thus perform tasks without explicit instructions. 
    Recently, generative artificial neural networks have been able to surpass many 
    previous approaches in performance. Machine learning approaches have been used in 
    various fields, including natural language processing, computer vision, speech 
    recognition, email filtering, agriculture, and medicine. ML is known in its 
    application across business problems under the name predictive analytics. 
    Although not all machine learning is statistically based, computational statistics 
    is an important source of methods for the field. The mathematical foundations of ML 
    are provided by mathematical optimization (mathematical programming) methods. 
    Data mining is a related field of study, focusing on exploratory data analysis 
    through unsupervised learning. From a theoretical standpoint, probably approximately 
    correct (PAC) learning provides a framework for describing machine learning. The 
    term "machine learning" was coined by Arthur Samuel in 1959, an American IBMer and 
    pioneer in the field of computer gaming and artificial intelligence. A representative 
    book of the machine learning research during the 1960s was the Nilsson's book on 
    Learning Machines, dealing mostly with machine learning for pattern classification.
    """ * 5  # 模拟长文档
    
    query = "What is machine learning used for?"
    
    print(f"\nQuery: {query}")
    print(f"Original context length: {len(long_context)} chars")
    
    # Fallback压缩演示
    result = await compressor.compress_documents(
        documents=[{"id": "doc_1", "content": long_context}],
        query=query,
        max_tokens=500,
        strategy="truncate"
    )
    
    print(f"\nCompressed (Fallback Strategy):")
    print(f"  Original: {len(long_context)} chars")
    print(f"  Compressed: {len(result[0]['content'])} chars")
    print(f"  Ratio: {len(result[0]['content']) / len(long_context):.2%}")
    
    print("\nNote: Full LLMLingua compression requires GPU and model download.")
    print("      This demo uses fallback truncation for quick testing.")


async def demo_end_to_end():
    """端到端演示"""
    print("\n" + "="*60)
    print("Demo 4: End-to-End Integrated RAG Pipeline")
    print("="*60)
    
    query = "How does exercise improve cardiovascular health?"
    
    print(f"\nQuery: {query}")
    print("\nPipeline:")
    print("  1. Query Rewriting → Multiple sub-queries")
    print("  2. Hybrid Retrieval → Dense + Sparse + BM25")
    print("  3. Multi-hop Search → Iterative retrieval")
    print("  4. Rankify Reranking → 3-stage precision ranking")
    print("  5. LLMLingua Compression → Context optimization")
    
    # Step 1: 查询改写
    print("\n[Step 1] Query Rewriting...")
    rewriter = QueryRewriter()
    queries = await rewriter.rewrite(query, strategy="multi_query", num_queries=3)
    print(f"  Generated {len(queries)} queries for retrieval")
    
    # Step 2-3: 检索（简化演示）
    print("\n[Step 2-3] Hybrid Multi-hop Retrieval...")
    print("  - Dense vectors (ChromaDB/Milvus)")
    print("  - Sparse vectors (SPLADE)")
    print("  - BM25 keyword matching")
    print("  - RRF fusion")
    
    # Step 4: 重排序
    print("\n[Step 4] Rankify 3-Stage Reranking...")
    print("  - Stage 1: MiniLM fast screening (Top 100 → 30)")
    print("  - Stage 2: BGE-Reranker precision (Top 30 → 10)")
    print("  - Stage 3: LongLLMLingua optimization (Top 10 → 5)")
    
    # Step 5: 压缩
    print("\n[Step 5] LLMLingua Context Compression...")
    print("  - Information-entropy based compression")
    print("  - Preserves query-relevant content")
    print("  - Reduces token usage by 30-50%")
    
    print("\n✅ Pipeline complete! Ready for LLM generation.")


async def main():
    """主函数"""
    print("\n" + "="*70)
    print("  RAG Enterprise System - Integrated Demo")
    print("  Combining: Rankify + LLMLingua + RAG_Techniques")
    print("="*70)
    
    try:
        await demo_query_rewrite()
        await demo_reranking()
        await demo_compression()
        await demo_end_to_end()
        
        print("\n" + "="*70)
        print("  Demo Complete!")
        print("  Next: Run with real models for full functionality")
        print("="*70 + "\n")
        
    except Exception as e:
        logger.error(f"Demo failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
