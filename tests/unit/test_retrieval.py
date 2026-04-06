"""
Unit Tests for Retrieval Module - 检索模块单元测试
"""
import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
import numpy as np

from src.retrieval.hybrid import HybridRetriever, RRFFusion, DenseRetriever, SparseRetriever


class TestRRFFusion:
    """测试RRF融合算法"""
    
    def test_rrf_basic(self):
        """测试基本的RRF融合"""
        fusion = RRFFusion(k=60)
        
        # 模拟两个检索器的结果
        results_a = [
            {"id": "doc1", "score": 0.9},
            {"id": "doc2", "score": 0.8},
            {"id": "doc3", "score": 0.7},
        ]
        
        results_b = [
            {"id": "doc2", "score": 0.95},
            {"id": "doc1", "score": 0.85},
            {"id": "doc4", "score": 0.75},
        ]
        
        fused = fusion.fuse([results_a, results_b], top_k=3)
        
        assert len(fused) == 3
        # doc1和doc2在两种结果中都出现，应该排在前面
        assert fused[0]["id"] in ["doc1", "doc2"]
        
    def test_rrf_empty_results(self):
        """测试空结果处理"""
        fusion = RRFFusion()
        
        fused = fusion.fuse([], top_k=5)
        assert fused == []
        
        fused = fusion.fuse([[]], top_k=5)
        assert fused == []


class TestDenseRetriever:
    """测试稠密向量检索"""
    
    @pytest.fixture
    def mock_encoder(self):
        """模拟编码器"""
        encoder = Mock()
        encoder.encode = Mock(return_value=np.random.randn(768).astype(np.float32))
        return encoder
    
    @pytest.fixture
    def mock_vector_store(self):
        """模拟向量存储"""
        store = Mock()
        store.search = Mock(return_value=[
            {"id": "doc1", "score": 0.9, "content": "test1"},
            {"id": "doc2", "score": 0.8, "content": "test2"},
        ])
        return store
    
    @pytest.mark.asyncio
    async def test_retrieve(self, mock_encoder, mock_vector_store):
        """测试检索功能"""
        retriever = DenseRetriever(
            encoder=mock_encoder,
            vector_store=mock_vector_store
        )
        
        results = await retriever.retrieve("test query", top_k=5)
        
        assert len(results) == 2
        assert results[0]["id"] == "doc1"
        mock_encoder.encode.assert_called_once()
        mock_vector_store.search.assert_called_once()


class TestHybridRetriever:
    """测试混合检索"""
    
    @pytest.fixture
    def retriever(self):
        """创建混合检索器实例"""
        with patch('src.retrieval.dense.DenseRetriever') as mock_dense, \
             patch('src.retrieval.sparse.SparseRetriever') as mock_sparse:
            
            # 配置mock
            mock_dense_instance = AsyncMock()
            mock_dense_instance.retrieve = AsyncMock(return_value=[
                {"id": "doc1", "score": 0.9, "content": "dense1"},
                {"id": "doc2", "score": 0.8, "content": "dense2"},
            ])
            mock_dense.return_value = mock_dense_instance
            
            mock_sparse_instance = AsyncMock()
            mock_sparse_instance.retrieve = AsyncMock(return_value=[
                {"id": "doc2", "score": 0.95, "content": "sparse1"},
                {"id": "doc3", "score": 0.7, "content": "sparse2"},
            ])
            mock_sparse.return_value = mock_sparse_instance
            
            retriever = HybridRetriever()
            retriever.dense_retriever = mock_dense_instance
            retriever.sparse_retriever = mock_sparse_instance
            
            yield retriever
    
    @pytest.mark.asyncio
    async def test_hybrid_retrieve(self, retriever):
        """测试混合检索"""
        results = await retriever.retrieve(
            queries=["test query"],
            top_k=5
        )
        
        assert len(results) > 0
        # 验证多路检索被调用
        retriever.dense_retriever.retrieve.assert_called()
        retriever.sparse_retriever.retrieve.assert_called()


class TestQueryRewrite:
    """测试查询改写"""
    
    @pytest.mark.asyncio
    async def test_hyde_rewriter(self):
        """测试HyDE改写"""
        from src.retrieval.rewrite.hyde import HyDERewriter
        
        mock_llm = AsyncMock()
        mock_llm.generate = AsyncMock(return_value="假设文档内容")
        
        rewriter = HyDERewriter(llm=mock_llm)
        result = await rewriter.generate("测试查询")
        
        assert result == "假设文档内容"
        mock_llm.generate.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_multi_query_generator(self):
        """测试Multi-Query生成"""
        from src.retrieval.rewrite.multi_query import MultiQueryGenerator
        
        mock_llm = AsyncMock()
        mock_llm.generate = AsyncMock(return_value="""
        1. RAG优化方法有哪些
        2. 如何提升检索效果
        3. RAG系统调优技巧
        """)
        
        generator = MultiQueryGenerator(llm=mock_llm, num_queries=3)
        queries = await generator.generate("RAG优化")
        
        assert len(queries) == 3
        assert all("RAG" in q or "检索" in q or "调优" in q for q in queries)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
