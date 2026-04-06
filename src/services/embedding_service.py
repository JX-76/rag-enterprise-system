"""
Embedding Service - 向量化服务

支持:
- BAAI/bge-small-zh-v1.5 (默认，轻量高效)
- 其他sentence-transformers模型
- ChromaDB向量存储
- 批量编码
"""
import os
import hashlib
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

# 尝试导入torch/transformers
try:
    import torch
    import numpy as np
    from sentence_transformers import SentenceTransformer
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    torch = None
    np = None
    SentenceTransformer = None

# 尝试导入ChromaDB
try:
    import chromadb
    from chromadb.config import Settings
    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False
    chromadb = None


@dataclass
class EmbeddingConfig:
    """Embedding配置"""
    model_name: str = "BAAI/bge-small-zh-v1.5"
    device: str = "cpu"  # cpu/cuda
    normalize_embeddings: bool = True
    batch_size: int = 32
    max_seq_length: int = 512


@dataclass
class VectorStoreConfig:
    """向量存储配置"""
    persist_directory: str = "./chroma_db"
    collection_name: str = "documents"
    distance_fn: str = "cosine"  # cosine/l2/ip


class EmbeddingService:
    """
    向量化服务
    
    使用示例:
        service = EmbeddingService()
        embeddings = service.encode(["文本1", "文本2"])
    """
    
    def __init__(self, config: Optional[EmbeddingConfig] = None):
        self.config = config or EmbeddingConfig()
        self._model = None
        self._model_loaded = False
        
        if not TORCH_AVAILABLE:
            logger.warning("torch/sentence-transformers not installed. "
                          "Install: pip install torch sentence-transformers")
    
    def _load_model(self):
        """加载模型"""
        if not TORCH_AVAILABLE:
            raise ImportError("sentence-transformers required")
        
        if self._model_loaded:
            return
        
        logger.info(f"Loading embedding model: {self.config.model_name}")
        
        self._model = SentenceTransformer(
            self.config.model_name,
            device=self.config.device
        )
        self._model.max_seq_length = self.config.max_seq_length
        self._model_loaded = True
        
        logger.info(f"Model loaded on {self.config.device}")
    
    def encode(
        self,
        texts: Union[str, List[str]],
        show_progress: bool = False
    ) -> List[List[float]]:
        """
        编码文本
        
        Args:
            texts: 单个文本或文本列表
            show_progress: 是否显示进度条
        
        Returns:
            嵌入向量列表
        """
        if not TORCH_AVAILABLE:
            raise ImportError("sentence-transformers not installed")
        
        self._load_model()
        
        # 确保是列表
        if isinstance(texts, str):
            texts = [texts]
        
        # 过滤空文本
        texts = [t.strip() if t else "" for t in texts]
        
        # 编码
        embeddings = self._model.encode(
            texts,
            batch_size=self.config.batch_size,
            show_progress_bar=show_progress,
            normalize_embeddings=self.config.normalize_embeddings,
            convert_to_numpy=True
        )
        
        return embeddings.tolist()
    
    def encode_queries(self, queries: List[str]) -> List[List[float]]:
        """编码查询（添加指令）"""
        # BGE模型推荐为查询添加指令
        instructed_queries = [
            f"Represent this sentence for searching relevant passages: {q}"
            for q in queries
        ]
        return self.encode(instructed_queries)
    
    def similarity(
        self,
        query_embedding: List[float],
        doc_embeddings: List[List[float]]
    ) -> List[float]:
        """
        计算相似度（余弦相似度）
        """
        if not np:
            raise ImportError("numpy not installed")
        
        query = np.array(query_embedding)
        docs = np.array(doc_embeddings)
        
        # 归一化
        query_norm = query / np.linalg.norm(query)
        docs_norm = docs / np.linalg.norm(docs, axis=1, keepdims=True)
        
        # 余弦相似度
        similarities = np.dot(docs_norm, query_norm)
        
        return similarities.tolist()
    
    def get_model_info(self) -> Dict[str, Any]:
        """获取模型信息"""
        if not self._model_loaded:
            return {"status": "not_loaded", "model_name": self.config.model_name}
        
        return {
            "status": "loaded",
            "model_name": self.config.model_name,
            "device": self.config.device,
            "max_seq_length": self.config.max_seq_length,
            "embedding_dim": self._model.get_sentence_embedding_dimension()
        }


class VectorStore:
    """
    向量存储服务 (ChromaDB)
    
    使用示例:
        store = VectorStore()
        store.add_documents([{"id": "1", "text": "内容", "embedding": [...]}])
        results = store.search(query_embedding, top_k=5)
    """
    
    def __init__(self, config: Optional[VectorStoreConfig] = None):
        self.config = config or VectorStoreConfig()
        self._client = None
        self._collection = None
        
        if not CHROMA_AVAILABLE:
            logger.warning("chromadb not installed. "
                          "Install: pip install chromadb")
    
    def _init_client(self):
        """初始化客户端"""
        if not CHROMA_AVAILABLE:
            raise ImportError("chromadb required")
        
        if self._client is not None:
            return
        
        # 创建持久化目录
        os.makedirs(self.config.persist_directory, exist_ok=True)
        
        self._client = chromadb.Client(Settings(
            persist_directory=self.config.persist_directory,
            anonymized_telemetry=False
        ))
        
        # 获取或创建集合
        self._collection = self._client.get_or_create_collection(
            name=self.config.collection_name,
            metadata={"hnsw:space": self.config.distance_fn}
        )
        
        logger.info(f"Vector store initialized: {self.config.collection_name}")
    
    def add_documents(
        self,
        documents: List[Dict[str, Any]],
        embeddings: List[List[float]]
    ):
        """
        添加文档
        
        Args:
            documents: [{"id": str, "text": str, "metadata": dict}, ...]
            embeddings: 对应的嵌入向量
        """
        self._init_client()
        
        ids = [doc["id"] for doc in documents]
        texts = [doc["text"] for doc in documents]
        metadatas = [doc.get("metadata", {}) for doc in documents]
        
        self._collection.add(
            ids=ids,
            documents=texts,
            embeddings=embeddings,
            metadatas=metadatas
        )
        
        logger.info(f"Added {len(documents)} documents to vector store")
    
    def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        filter_dict: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        向量搜索
        
        Args:
            query_embedding: 查询向量
            top_k: 返回结果数
            filter_dict: 元数据过滤条件
        
        Returns:
            [{"id": str, "text": str, "score": float, "metadata": dict}, ...]
        """
        self._init_client()
        
        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=filter_dict
        )
        
        # 格式化结果
        formatted = []
        for i in range(len(results["ids"][0])):
            formatted.append({
                "id": results["ids"][0][i],
                "text": results["documents"][0][i],
                "score": float(results["distances"][0][i]),
                "metadata": results["metadatas"][0][i] if results["metadatas"] else {}
            })
        
        return formatted
    
    def delete(self, ids: List[str]):
        """删除文档"""
        self._init_client()
        self._collection.delete(ids=ids)
        logger.info(f"Deleted {len(ids)} documents")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        self._init_client()
        count = self._collection.count()
        return {
            "collection_name": self.config.collection_name,
            "document_count": count,
            "persist_directory": self.config.persist_directory
        }
    
    def persist(self):
        """持久化数据"""
        if self._client:
            # ChromaDB自动持久化
            logger.info("Data persisted")


class RAGIngestionPipeline:
    """
    RAG文档入库Pipeline
    
    使用示例:
        pipeline = RAGIngestionPipeline()
        pipeline.ingest_file("document.pdf")
    """
    
    def __init__(
        self,
        embedding_config: Optional[EmbeddingConfig] = None,
        vector_config: Optional[VectorStoreConfig] = None
    ):
        self.embedding_service = EmbeddingService(embedding_config)
        self.vector_store = VectorStore(vector_config)
    
    def ingest_documents(
        self,
        documents: List[Dict[str, str]],
        batch_size: int = 32
    ):
        """
        批量入库文档
        
        Args:
            documents: [{"id": str, "text": str, "metadata": dict}, ...]
        """
        texts = [doc["text"] for doc in documents]
        
        # 批量编码
        logger.info(f"Encoding {len(texts)} documents...")
        embeddings = self.embedding_service.encode(
            texts,
            show_progress=True
        )
        
        # 入库
        self.vector_store.add_documents(documents, embeddings)
        
        logger.info(f"Ingested {len(documents)} documents")
    
    def search(
        self,
        query: str,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        搜索
        
        Args:
            query: 查询文本
            top_k: 返回结果数
        
        Returns:
            检索结果列表
        """
        # 编码查询
        query_embedding = self.embedding_service.encode_queries([query])[0]
        
        # 搜索
        return self.vector_store.search(query_embedding, top_k)


# 便捷函数
def get_embedding_service(
    model_name: str = "BAAI/bge-small-zh-v1.5",
    device: str = "cpu"
) -> EmbeddingService:
    """获取向量化服务实例"""
    config = EmbeddingConfig(
        model_name=model_name,
        device=device
    )
    return EmbeddingService(config)


def get_vector_store(
    persist_dir: str = "./chroma_db",
    collection: str = "documents"
) -> VectorStore:
    """获取向量存储实例"""
    config = VectorStoreConfig(
        persist_directory=persist_dir,
        collection_name=collection
    )
    return VectorStore(config)
