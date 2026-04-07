"""
Milvus 向量数据库实现
支持文档的增删改查和向量搜索
"""
from typing import List, Dict, Any, Optional
import logging
from tenacity import retry, stop_after_attempt, wait_fixed

from .base import VectorDB, VectorDBError, SearchResult

try:
    from pymilvus import connections, FieldSchema, CollectionSchema, DataType, Collection, utility
    MILVUS_AVAILABLE = True
except ImportError:
    MILVUS_AVAILABLE = False
    logging.warning("pymilvus 未安装，Milvus 功能不可用")

logger = logging.getLogger(__name__)


class MilvusStore(VectorDB):
    """
    Milvus 向量存储实现
    
    特性：
    - 自动连接管理
    - 连接池复用
    - 重试机制
    - 支持元数据过滤
    """
    
    def __init__(
        self,
        collection_name: str = "rag_documents",
        dimension: int = 768,
        host: str = "localhost",
        port: int = 19530,
        alias: str = "default"
    ):
        """
        Args:
            collection_name: 集合名称
            dimension: 向量维度（BGE-small=768）
            host: Milvus 主机
            port: Milvus 端口
            alias: 连接别名
        """
        super().__init__(collection_name, dimension)
        self.host = host
        self.port = port
        self.alias = alias
        self._collection = None
        
        if not MILVUS_AVAILABLE:
            raise VectorDBError("pymilvus 未安装，请运行: pip install pymilvus")
    
    @retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
    def connect(self) -> bool:
        """
        连接 Milvus
        
        使用重试机制，避免偶发连接失败
        """
        try:
            # 检查是否已连接
            if self._connected:
                return True
            
            # 建立连接
            connections.connect(
                alias=self.alias,
                host=self.host,
                port=self.port
            )
            
            self._connected = True
            logger.info(f"Milvus 连接成功: {self.host}:{self.port}")
            
            # 初始化集合
            self._init_collection()
            
            return True
            
        except Exception as e:
            logger.error(f"Milvus 连接失败: {e}")
            raise VectorDBError(f"连接失败: {str(e)}")
    
    def disconnect(self) -> bool:
        """断开连接"""
        try:
            if self._connected:
                connections.disconnect(self.alias)
                self._connected = False
                logger.info("Milvus 连接已关闭")
            return True
        except Exception as e:
            logger.error(f"断开连接失败: {e}")
            return False
    
    def _init_collection(self):
        """初始化集合（如果不存在则创建）"""
        try:
            # 检查集合是否存在
            if utility.has_collection(self.collection_name, using=self.alias):
                self._collection = Collection(self.collection_name, using=self.alias)
                logger.info(f"集合已存在: {self.collection_name}")
            else:
                # 创建集合
                self._create_collection()
            
            # 加载集合到内存
            self._collection.load()
            
        except Exception as e:
            logger.error(f"初始化集合失败: {e}")
            raise VectorDBError(f"初始化集合失败: {str(e)}")
    
    def _create_collection(self):
        """创建集合"""
        # 定义字段
        fields = [
            FieldSchema(name="id", dtype=DataType.VARCHAR, max_length=128, is_primary=True),
            FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=self.dimension),
            FieldSchema(name="doc_id", dtype=DataType.VARCHAR, max_length=128),
            FieldSchema(name="chunk_index", dtype=DataType.INT32),
            FieldSchema(name="filename", dtype=DataType.VARCHAR, max_length=256),
        ]
        
        # 创建 schema
        schema = CollectionSchema(fields, description="RAG 文档集合")
        
        # 创建集合
        self._collection = Collection(
            name=self.collection_name,
            schema=schema,
            using=self.alias
        )
        
        # 创建索引
        self._create_index()
        
        logger.info(f"集合创建成功: {self.collection_name}")
    
    def _create_index(self):
        """创建向量索引"""
        try:
            index_params = {
                "index_type": "IVF_FLAT",  # 简单高效的索引类型
                "metric_type": "COSINE",   # 余弦相似度
                "params": {"nlist": 128}   # 聚类中心数
            }
            
            self._collection.create_index(
                field_name="embedding",
                index_params=index_params
            )
            
            logger.info("向量索引创建成功")
            
        except Exception as e:
            logger.error(f"创建索引失败: {e}")
            raise
    
    def add(
        self,
        ids: List[str],
        texts: List[str],
        embeddings: List[List[float]],
        metadatas: Optional[List[Dict[str, Any]]] = None
    ) -> bool:
        """
        添加文档向量
        
        Args:
            ids: 文档ID列表
            texts: 文本内容列表
            embeddings: 向量列表
            metadatas: 元数据列表（包含 doc_id, chunk_index, filename）
        """
        if not self._connected:
            self.connect()
        
        try:
            # 准备数据
            doc_ids = [m.get("doc_id", "") for m in (metadatas or [])]
            chunk_indices = [m.get("chunk_index", 0) for m in (metadatas or [])]
            filenames = [m.get("filename", "") for m in (metadatas or [])]
            
            # 插入数据
            entities = [
                ids,
                texts,
                embeddings,
                doc_ids,
                chunk_indices,
                filenames
            ]
            
            self._collection.insert(entities)
            self._collection.flush()
            
            logger.info(f"添加 {len(ids)} 条文档向量")
            return True
            
        except Exception as e:
            logger.error(f"添加文档失败: {e}")
            raise VectorDBError(f"添加失败: {str(e)}")
    
    def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        filter_expr: Optional[str] = None
    ) -> List[SearchResult]:
        """
        向量搜索
        
        Args:
            query_embedding: 查询向量
            top_k: 返回结果数
            filter_expr: 过滤表达式（如：doc_id == 'xxx'）
        
        Returns:
            搜索结果列表
        """
        if not self._connected:
            self.connect()
        
        try:
            # 搜索参数
            search_params = {
                "metric_type": "COSINE",
                "params": {"nprobe": 10}
            }
            
            # 执行搜索
            results = self._collection.search(
                data=[query_embedding],
                anns_field="embedding",
                param=search_params,
                limit=top_k,
                expr=filter_expr,
                output_fields=["id", "text", "doc_id", "chunk_index", "filename"]
            )
            
            # 解析结果
            search_results = []
            for hits in results:
                for hit in hits:
                    result = SearchResult(
                        id=hit.id,
                        text=hit.entity.get("text", ""),
                        score=hit.score,
                        metadata={
                            "doc_id": hit.entity.get("doc_id"),
                            "chunk_index": hit.entity.get("chunk_index"),
                            "filename": hit.entity.get("filename")
                        }
                    )
                    search_results.append(result)
            
            return search_results
            
        except Exception as e:
            logger.error(f"搜索失败: {e}")
            raise VectorDBError(f"搜索失败: {str(e)}")
    
    def delete(self, ids: List[str]) -> bool:
        """删除文档"""
        if not self._connected:
            self.connect()
        
        try:
            # 构建删除表达式
            id_list = ', '.join([f'"{id_}"' for id_ in ids])
            expr = f'id in [{id_list}]'
            
            self._collection.delete(expr)
            self._collection.flush()
            
            logger.info(f"删除 {len(ids)} 条文档")
            return True
            
        except Exception as e:
            logger.error(f"删除失败: {e}")
            raise VectorDBError(f"删除失败: {str(e)}")
    
    def update(
        self,
        ids: List[str],
        texts: List[str],
        embeddings: List[List[float]],
        metadatas: Optional[List[Dict[str, Any]]] = None
    ) -> bool:
        """
        更新文档（先删除后插入）
        """
        try:
            # 删除旧数据
            self.delete(ids)
            # 插入新数据
            self.add(ids, texts, embeddings, metadatas)
            
            logger.info(f"更新 {len(ids)} 条文档")
            return True
            
        except Exception as e:
            logger.error(f"更新失败: {e}")
            raise VectorDBError(f"更新失败: {str(e)}")
    
    def clear(self) -> bool:
        """清空集合"""
        if not self._connected:
            self.connect()
        
        try:
            # 删除所有数据
            self._collection.delete("id != ''")
            self._collection.flush()
            
            logger.info("集合已清空")
            return True
            
        except Exception as e:
            logger.error(f"清空失败: {e}")
            raise VectorDBError(f"清空失败: {str(e)}")
    
    def count(self) -> int:
        """获取文档数量"""
        if not self._connected:
            self.connect()
        
        try:
            return self._collection.num_entities
        except Exception as e:
            logger.error(f"获取数量失败: {e}")
            return 0
    
    def delete_by_doc_id(self, doc_id: str) -> bool:
        """
        根据文档ID删除所有相关块
        
        Args:
            doc_id: 文档ID
        """
        if not self._connected:
            self.connect()
        
        try:
            expr = f'doc_id == "{doc_id}"'
            self._collection.delete(expr)
            self._collection.flush()
            
            logger.info(f"删除文档 {doc_id} 的所有向量")
            return True
            
        except Exception as e:
            logger.error(f"删除文档失败: {e}")
            raise VectorDBError(f"删除失败: {str(e)}")
