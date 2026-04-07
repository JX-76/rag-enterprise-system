"""
Embedding服务
文本向量化，使用BGE模型
"""
from typing import List
import logging
import numpy as np

try:
    from sentence_transformers import SentenceTransformer
    EMBEDDING_AVAILABLE = True
except ImportError:
    EMBEDDING_AVAILABLE = False

logger = logging.getLogger(__name__)


class EmbeddingService:
    """
    Embedding服务
    
    使用BGE-small模型，768维向量
    支持batch编码，提高性能
    """
    
    def __init__(self, model_name: str = "BAAI/bge-small-zh-v1.5", device: str = "cpu"):
        """
        Args:
            model_name: 模型名称
            device: cpu/cuda
        """
        if not EMBEDDING_AVAILABLE:
            raise ImportError("sentence-transformers未安装，请运行: pip install sentence-transformers")
        
        self.model_name = model_name
        self.device = device
        self.model = None
        self._load_model()
    
    def _load_model(self):
        """加载模型"""
        try:
            logger.info(f"加载Embedding模型: {self.model_name}")
            self.model = SentenceTransformer(self.model_name, device=self.device)
            self.dimension = self.model.get_sentence_embedding_dimension()
            logger.info(f"模型加载成功，维度: {self.dimension}")
        except Exception as e:
            logger.error(f"模型加载失败: {e}")
            raise
    
    def encode(self, texts: List[str], batch_size: int = 32) -> List[List[float]]:
        """
        编码文本
        
        Args:
            texts: 文本列表
            batch_size: 批大小
        
        Returns:
            向量列表
        """
        if not texts:
            return []
        
        try:
            # 清理文本
            texts = [str(t).strip() for t in texts if t and str(t).strip()]
            
            if not texts:
                return []
            
            # 编码
            embeddings = self.model.encode(
                texts,
                batch_size=batch_size,
                show_progress_bar=len(texts) > 10,
                convert_to_numpy=True
            )
            
            # 转为列表
            return embeddings.tolist()
            
        except Exception as e:
            logger.error(f"编码失败: {e}")
            raise
    
    def encode_query(self, query: str) -> List[float]:
        """
        编码查询（添加instruction）
        
        BGE模型推荐为查询添加instruction以获得更好效果
        """
        # BGE中文指令
        instruction = "为这个句子生成表示以用于检索相关文章："
        query_with_instruction = instruction + query
        
        embeddings = self.encode([query_with_instruction])
        return embeddings[0] if embeddings else []


# 便捷函数
def get_embedding_service() -> EmbeddingService:
    """获取Embedding服务实例"""
    return EmbeddingService()
