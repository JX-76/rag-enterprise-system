"""
FAISS Vector Store - FAISS向量存储
支持HNSW索引、增量更新、批量操作
"""
import asyncio
import os
import pickle
from typing import List, Dict, Any, Optional
import numpy as np
import faiss
from pathlib import Path
import json

from src.core.config import settings
from src.core.logging import get_logger

logger = get_logger(__name__)


class FAISSVectorStore:
    """
    FAISS向量存储
    
    特性：
    - HNSW索引（高速近似检索）
    - 增量更新
    - 持久化存储
    - 元数据管理
    """
    
    def __init__(self, index_path: Optional[str] = None):
        self.index_path = index_path or "./data/vector_index"
        self.dimension = 1024  # BGE-large dimension
        self.index = None
        self.metadata: Dict[str, Dict] = {}
        self.id_mapping: Dict[int, str] = {}  # faiss id -> doc id
        self._lock = asyncio.Lock()
        
        self._ensure_dir()
        self._load_or_create()
    
    def _ensure_dir(self):
        """确保目录存在"""
        Path(self.index_path).parent.mkdir(parents=True, exist_ok=True)
    
    def _load_or_create(self):
        """加载或创建索引"""
        index_file = Path(self.index_path) / "index.faiss"
        meta_file = Path(self.index_path) / "metadata.json"
        
        if index_file.exists():
            try:
                self.index = faiss.read_index(str(index_file))
                logger.info(f"Loaded existing index from {index_file}")
                
                # 加载元数据
                if meta_file.exists():
                    with open(meta_file, 'r') as f:
                        data = json.load(f)
                        self.metadata = data.get('metadata', {})
                        self.id_mapping = {
                            int(k): v for k, v in data.get('id_mapping', {}).items()
                        }
                    
                logger.info(f"Loaded {len(self.metadata)} documents")
                
            except Exception as e:
                logger.error(f"Failed to load index: {e}, creating new")
                self._create_new_index()
        else:
            self._create_new_index()
    
    def _create_new_index(self):
        """创建新索引"""
        # HNSW索引：高速近似最近邻搜索
        self.index = faiss.IndexHNSWFlat(self.dimension, 32)
        self.index.hnsw.efConstruction = 128
        self.index.hnsw.efSearch = 64
        logger.info("Created new HNSW index")
    
    async def add(
        self,
        documents: List[Dict[str, Any]],
        embeddings: np.ndarray
    ):
        """
        添加文档
        
        Args:
            documents: 文档列表，每个包含id和content
            embeddings: 对应的embedding向量 [N, D]
        """
        async with self._lock:
            if len(documents) != len(embeddings):
                raise ValueError("Documents and embeddings must have same length")
            
            if len(documents) == 0:
                return
            
            # 确保是float32
            embeddings = embeddings.astype(np.float32)
            
            # 获取当前索引大小
            start_id = self.index.ntotal
            
            # 添加到FAISS
            self.index.add(embeddings)
            
            # 更新元数据
            for i, doc in enumerate(documents):
                faiss_id = start_id + i
                doc_id = doc['id']
                self.id_mapping[faiss_id] = doc_id
                self.metadata[doc_id] = {
                    'content': doc.get('content', ''),
                    'metadata': doc.get('metadata', {}),
                    'faiss_id': faiss_id
                }
            
            logger.info(f"Added {len(documents)} documents to index")
            
            # 异步保存
            asyncio.create_task(self._save_async())
    
    async def search(
        self,
        vector: np.ndarray,
        top_k: int = 10,
        filter_dict: Optional[Dict] = None
    ) -> List[Dict[str, Any]]:
        """
        向量检索
        
        Args:
            vector: 查询向量 [D] 或 [1, D]
            top_k: 返回结果数
            filter_dict: 过滤条件
        """
        async with self._lock:
            if self.index.ntotal == 0:
                return []
            
            # 确保向量形状正确
            if vector.ndim == 1:
                vector = vector.reshape(1, -1)
            vector = vector.astype(np.float32)
            
            # 检索
            distances, indices = self.index.search(vector, top_k)
            
            results = []
            for i, (dist, idx) in enumerate(zip(distances[0], indices[0])):
                if idx == -1:  # FAISS返回-1表示无效
                    continue
                
                doc_id = self.id_mapping.get(int(idx))
                if not doc_id:
                    continue
                
                meta = self.metadata.get(doc_id, {})
                
                # 过滤
                if filter_dict and not self._matches_filter(meta, filter_dict):
                    continue
                
                results.append({
                    'id': doc_id,
                    'content': meta.get('content', ''),
                    'score': float(1 / (1 + dist)),  # 转换为相似度
                    'metadata': meta.get('metadata', {})
                })
            
            return results
    
    def _matches_filter(self, meta: Dict, filter_dict: Dict) -> bool:
        """检查是否匹配过滤条件"""
        doc_meta = meta.get('metadata', {})
        for key, value in filter_dict.items():
            if doc_meta.get(key) != value:
                return False
        return True
    
    async def delete(self, doc_ids: List[str]):
        """
        删除文档
        
        注意：FAISS不支持直接删除，使用标记删除
        """
        async with self._lock:
            for doc_id in doc_ids:
                if doc_id in self.metadata:
                    # 标记为已删除
                    self.metadata[doc_id]['deleted'] = True
                    logger.debug(f"Marked document {doc_id} as deleted")
    
    async def _save_async(self):
        """异步保存索引"""
        try:
            await asyncio.get_event_loop().run_in_executor(
                None, self._save_sync
            )
        except Exception as e:
            logger.error(f"Failed to save index: {e}")
    
    def _save_sync(self):
        """同步保存索引"""
        index_file = Path(self.index_path) / "index.faiss"
        meta_file = Path(self.index_path) / "metadata.json"
        
        # 保存FAISS索引
        faiss.write_index(self.index, str(index_file))
        
        # 保存元数据
        with open(meta_file, 'w') as f:
            json.dump({
                'metadata': self.metadata,
                'id_mapping': {str(k): v for k, v in self.id_mapping.items()}
            }, f, ensure_ascii=False, indent=2)
        
        logger.debug(f"Index saved: {len(self.metadata)} documents")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取索引统计"""
        return {
            'total_documents': self.index.ntotal,
            'dimension': self.dimension,
            'active_documents': sum(
                1 for m in self.metadata.values() if not m.get('deleted', False)
            )
        }


# 全局实例
_vector_store: Optional[FAISSVectorStore] = None


def get_vector_store() -> FAISSVectorStore:
    """获取全局向量存储实例"""
    global _vector_store
    if _vector_store is None:
        _vector_store = FAISSVectorStore()
    return _vector_store
