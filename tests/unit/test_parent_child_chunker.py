"""
父子分块单元测试
测试 ParentChildChunker 的各种分块场景
"""
import pytest

from src.ingestion.parent_child_chunker import (
    ParentChildChunker,
    ParentChunk,
    ChildChunk
)


class TestParentChildChunker:
    """父子分块器测试"""
    
    @pytest.fixture
    def chunker(self):
        """创建分块器实例"""
        return ParentChildChunker(
            parent_size=500,
            child_size=100,
            child_overlap=20
        )
    
    @pytest.fixture
    def sample_text(self):
        """测试文本"""
        return """
        Machine learning is a subset of artificial intelligence that enables 
        systems to learn and improve from experience without being explicitly 
        programmed. It focuses on the development of computer programs that 
        can access data and use it to learn for themselves.
        
        Deep learning is part of a broader family of machine learning methods 
        based on artificial neural networks. Learning can be supervised, 
        semi-supervised or unsupervised. Deep learning architectures have been 
        applied to fields including computer vision, speech recognition, 
        natural language processing, machine translation, bioinformatics, 
        drug design, medical image analysis, material inspection and board 
        game programs.
        
        Transformer is a deep learning model that adopts the mechanism of 
        attention, differentially weighting the significance of each part of 
        the input data. It is used primarily in the field of natural language 
        processing and computer vision. Like recurrent neural networks, 
        Transformers are designed to handle sequential input data.
        """ * 5  # 扩展文本
    
    def test_initialization(self, chunker):
        """测试初始化参数"""
        assert chunker.parent_size == 500
        assert chunker.child_size == 100
        assert chunker.child_overlap == 20
    
    def test_chunk_returns_parents(self, chunker, sample_text):
        """分块返回父块列表"""
        parents = chunker.chunk(sample_text)
        
        assert isinstance(parents, list)
        assert len(parents) > 0
        assert all(isinstance(p, ParentChunk) for p in parents)
    
    def test_parents_have_children(self, chunker, sample_text):
        """父块包含子块"""
        parents = chunker.chunk(sample_text)
        
        for parent in parents:
            assert len(parent.children) > 0
            assert all(isinstance(c, ChildChunk) for c in parent.children)
    
    def test_child_parent_relationship(self, chunker, sample_text):
        """子块正确关联父块"""
        parents = chunker.chunk(sample_text)
        
        for parent in parents:
            for child in parent.children:
                assert child.parent_id == parent.id
                assert child.parent is parent
    
    def test_child_size_constraint(self, chunker, sample_text):
        """子块大小符合约束"""
        parents = chunker.chunk(sample_text)
        
        for parent in parents:
            for child in parent.children:
                # 子块长度应该在目标大小附近
                # 由于是按字符数估计，允许一定误差
                child_len = len(child.content)
                assert child_len > 0
                assert child_len <= chunker.child_size * 2  # 允许一定超调
    
    def test_parent_size_constraint(self, chunker, sample_text):
        """父块大小符合约束"""
        parents = chunker.chunk(sample_text)
        
        for parent in parents:
            parent_len = len(parent.content)
            assert parent_len > 0
            # 父块大小应该在目标附近
            assert parent_len <= chunker.parent_size * 2
    
    def test_child_overlap(self, chunker, sample_text):
        """子块之间有重叠"""
        parents = chunker.chunk(sample_text)
        
        for parent in parents:
            if len(parent.children) >= 2:
                # 检查相邻子块是否有重叠
                for i in range(len(parent.children) - 1):
                    child1 = parent.children[i]
                    child2 = parent.children[i + 1]
                    
                    # 由于重叠，第二个子块的起始位置应该在前一个子块内部
                    assert child2.start_pos < child1.end_pos
    
    def test_child_full_context(self, chunker, sample_text):
        """子块可以获取完整上下文"""
        parents = chunker.chunk(sample_text)
        
        for parent in parents:
            for child in parent.children:
                full_context = child.get_full_context()
                assert full_context == parent.content
                assert len(full_context) >= len(child.content)
    
    def test_empty_text(self, chunker):
        """空文本处理"""
        parents = chunker.chunk("")
        assert len(parents) == 0
    
    def test_short_text(self, chunker):
        """短文本处理"""
        short_text = "This is a short text."
        parents = chunker.chunk(short_text)
        
        # 应该生成一个父块
        assert len(parents) >= 1
        assert len(parents[0].content) > 0
    
    def test_parent_chunk_metadata(self, chunker, sample_text):
        """父块包含元数据"""
        parents = chunker.chunk(sample_text)
        
        for parent in parents:
            assert parent.id is not None
            assert parent.start_pos >= 0
            assert parent.end_pos > parent.start_pos
            assert isinstance(parent.metadata, dict)
    
    def test_child_chunk_metadata(self, chunker, sample_text):
        """子块包含元数据"""
        parents = chunker.chunk(sample_text)
        
        for parent in parents:
            for child in parent.children:
                assert child.id is not None
                assert child.parent_id is not None
                assert child.start_pos >= 0
                assert child.end_pos > child.start_pos
                assert isinstance(child.metadata, dict)
    
    def test_chunk_id_uniqueness(self, chunker, sample_text):
        """所有ID唯一"""
        parents = chunker.chunk(sample_text)
        
        parent_ids = set()
        child_ids = set()
        
        for parent in parents:
            assert parent.id not in parent_ids
            parent_ids.add(parent.id)
            
            for child in parent.children:
                assert child.id not in child_ids
                child_ids.add(child.id)
    
    def test_parent_to_context(self, chunker, sample_text):
        """父块转换为上下文"""
        parents = chunker.chunk(sample_text)
        
        for parent in parents:
            context = parent.to_context()
            assert context == parent.content
            assert len(context) > 0
