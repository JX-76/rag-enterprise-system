"""
简易向量存储 - 轻量级实现

基于内存的向量存储，支持基本的增删改查和相似度搜索。
用于快速原型验证，生产环境可无缝切换到ChromaDB/Milvus。
"""
import json
import hashlib
import math
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass
from pathlib import Path
import pickle


@dataclass
class VectorDocument:
    """向量文档"""
    id: str
    text: str
    embedding: List[float]
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "text": self.text,
            "embedding": self.embedding,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VectorDocument":
        return cls(
            id=data["id"],
            text=data["text"],
            embedding=data["embedding"],
            metadata=data["metadata"]
        )


class SimpleVectorStore:
    """
    简易向量存储
    
    特点：
    - 纯Python实现，零依赖
    - 基于余弦相似度的向量检索
    - 支持持久化到磁盘
    - 支持增量更新和去重
    """
    
    def __init__(self, persist_path: Optional[str] = None):
        """
        初始化向量存储
        
        Args:
            persist_path: 持久化路径，为None则不持久化
        """
        self._docs: Dict[str, VectorDocument] = {}
        self._persist_path = persist_path
        
        # 如果有持久化路径，尝试加载
        if persist_path and Path(persist_path).exists():
            self._load()
    
    def add_document(
        self,
        text: str,
        embedding: List[float],
        metadata: Optional[Dict[str, Any]] = None,
        doc_id: Optional[str] = None
    ) -> str:
        """
        添加单个文档
        
        Args:
            text: 文档文本
            embedding: 向量表示
            metadata: 元数据
            doc_id: 指定文档ID，为None则自动生成
        
        Returns:
            doc_id: 文档ID
        """
        # 生成文档ID
        if doc_id is None:
            doc_id = hashlib.md5(text.encode()).hexdigest()[:16]
        
        # 检查是否已存在（基于内容去重）
        content_hash = hashlib.md5(text.encode()).hexdigest()
        for existing_doc in self._docs.values():
            if hashlib.md5(existing_doc.text.encode()).hexdigest() == content_hash:
                # 更新而不是重复添加
                existing_doc.embedding = embedding
                existing_doc.metadata.update(metadata or {})
                return existing_doc.id
        
        # 创建文档
        doc = VectorDocument(
            id=doc_id,
            text=text,
            embedding=embedding,
            metadata=metadata or {}
        )
        
        self._docs[doc_id] = doc
        return doc_id
    
    def add_documents(
        self,
        texts: List[str],
        embeddings: List[List[float]],
        metadatas: Optional[List[Dict[str, Any]]] = None
    ) -> List[str]:
        """
        批量添加文档
        
        Args:
            texts: 文档文本列表
            embeddings: 向量列表
            metadatas: 元数据列表
        
        Returns:
            doc_ids: 文档ID列表
        """
        if metadatas is None:
            metadatas = [{} for _ in texts]
        
        doc_ids = []
        for text, emb, meta in zip(texts, embeddings, metadatas):
            doc_id = self.add_document(text, emb, meta)
            doc_ids.append(doc_id)
        
        # 持久化
        self._persist()
        
        return doc_ids
    
    def search(
        self,
        query_embedding: List[float],
        top_k: int = 10,
        filter_dict: Optional[Dict[str, Any]] = None
    ) -> List[Tuple[VectorDocument, float]]:
        """
        相似度搜索
        
        Args:
            query_embedding: 查询向量
            top_k: 返回结果数
            filter_dict: 过滤条件
        
        Returns:
            文档和相似度分数的列表
        """
        if not self._docs:
            return []
        
        results = []
        
        for doc in self._docs.values():
            # 过滤
            if filter_dict:
                match = all(
                    doc.metadata.get(k) == v
                    for k, v in filter_dict.items()
                )
                if not match:
                    continue
            
            # 计算余弦相似度
            similarity = self._cosine_similarity(query_embedding, doc.embedding)
            results.append((doc, similarity))
        
        # 排序并返回top_k
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]
    
    def delete(self, doc_id: str) -> bool:
        """删除文档"""
        if doc_id in self._docs:
            del self._docs[doc_id]
            self._persist()
            return True
        return False
    
    def get(self, doc_id: str) -> Optional[VectorDocument]:
        """获取文档"""
        return self._docs.get(doc_id)
    
    def count(self) -> int:
        """文档数量"""
        return len(self._docs)
    
    def clear(self):
        """清空所有文档"""
        self._docs.clear()
        self._persist()
    
    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """计算余弦相似度"""
        if len(a) != len(b):
            return 0.0
        
        dot_product = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        
        if norm_a == 0 or norm_b == 0:
            return 0.0
        
        return dot_product / (norm_a * norm_b)
    
    def _persist(self):
        """持久化到磁盘"""
        if not self._persist_path:
            return
        
        Path(self._persist_path).parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            doc_id: doc.to_dict()
            for doc_id, doc in self._docs.items()
        }
        
        with open(self._persist_path, 'wb') as f:
            pickle.dump(data, f)
    
    def _load(self):
        """从磁盘加载"""
        try:
            with open(self._persist_path, 'rb') as f:
                data = pickle.load(f)
            
            for doc_id, doc_dict in data.items():
                self._docs[doc_id] = VectorDocument.from_dict(doc_dict)
        
        except Exception as e:
            print(f"加载向量存储失败: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "document_count": len(self._docs),
            "persist_path": self._persist_path,
            "vector_dim": len(next(iter(self._docs.values())).embedding) if self._docs else 0
        }
