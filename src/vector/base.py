"""
向量数据库抽象基类
定义统一接口，实现与具体向量库的解耦
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


class VectorDBError(Exception):
    """向量数据库异常"""
    pass


@dataclass
class SearchResult:
    """搜索结果"""
    id: str
    text: str
    score: float
    metadata: Dict[str, Any]


class VectorDB(ABC):
    """
    向量数据库抽象基类
    
    子类必须实现：
    - add: 添加文档向量
    - search: 向量搜索
    - delete: 删除文档
    - update: 更新文档
    - clear: 清空集合
    """
    
    def __init__(self, collection_name: str, dimension: int):
        """
        Args:
            collection_name: 集合名称
            dimension: 向量维度
        """
        self.collection_name = collection_name
        self.dimension = dimension
        self._connected = False
    
    @abstractmethod
    def connect(self) -> bool:
        """连接数据库"""
        pass
    
    @abstractmethod
    def disconnect(self) -> bool:
        """断开连接"""
        pass
    
    @abstractmethod
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
            metadatas: 元数据列表
        
        Returns:
            是否成功
        """
        pass
    
    @abstractmethod
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
            top_k: 返回结果数量
            filter_expr: 过滤表达式
        
        Returns:
            搜索结果列表
        """
        pass
    
    @abstractmethod
    def delete(self, ids: List[str]) -> bool:
        """
        删除文档
        
        Args:
            ids: 文档ID列表
        
        Returns:
            是否成功
        """
        pass
    
    @abstractmethod
    def update(
        self,
        ids: List[str],
        texts: List[str],
        embeddings: List[List[float]],
        metadatas: Optional[List[Dict[str, Any]]] = None
    ) -> bool:
        """
        更新文档
        
        Args:
            ids: 文档ID列表
            texts: 文本内容列表
            embeddings: 向量列表
            metadatas: 元数据列表
        
        Returns:
            是否成功
        """
        pass
    
    @abstractmethod
    def clear(self) -> bool:
        """清空集合"""
        pass
    
    @abstractmethod
    def count(self) -> int:
        """获取文档数量"""
        pass
    
    def health_check(self) -> bool:
        """健康检查"""
        try:
            return self._connected
        except:
            return False
