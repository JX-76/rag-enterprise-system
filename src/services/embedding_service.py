"""
Embedding Service - Embedding推理服务
支持BGE模型、批处理、GPU加速、连接池
"""
import asyncio
import numpy as np
from typing import List, Optional, Union
import torch
from sentence_transformers import SentenceTransformer
import hashlib
from functools import lru_cache

from src.core.config import settings
from src.core.logging import get_logger
from src.utils.cache import get_cache_manager, CacheManager

logger = get_logger(__name__)


class EmbeddingService:
    """
    Embedding服务

    特性：
    - 模型自动加载/卸载
    - 批处理优化
    - GPU加速
    - 本地缓存
    """

    def __init__(self):
        self.model: Optional[SentenceTransformer] = None
        self.model_name = settings.EMBEDDING_MODEL
        self.device = self._get_device()
        self.batch_size = 32
        self.cache = None
        self._lock = asyncio.Lock()
        self._initialized = False

    async def initialize(self):
        """异步初始化"""
        if self._initialized:
            return
        
        self.cache = await get_cache_manager()
        self._load_model()
        self._initialized = True
        logger.info("Embedding service initialized")

    def _get_device(self) -> str:
        """获取计算设备"""
        if torch.cuda.is_available():
            logger.info("Using GPU for embeddings")
            return "cuda"
        return "cpu"

    def _load_model(self):
        """加载模型"""
        logger.info(f"Loading embedding model: {self.model_name}")
        try:
            self.model = SentenceTransformer(
                self.model_name,
                device=self.device
            )
            logger.info(f"Model loaded. Dimension: {self.model.get_sentence_embedding_dimension()}")
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise

    async def encode(
        self,
        texts: Union[str, List[str]],
        normalize: bool = True,
        use_cache: bool = True
    ) -> np.ndarray:
        """
        编码文本

        Args:
            texts: 单条或多条文本
            normalize: 是否归一化
            use_cache: 是否使用缓存
        """
        if isinstance(texts, str):
            texts = [texts]

        if not texts:
            return np.array([])

        # 检查缓存
        if use_cache and len(texts) == 1:
            cached = await self._get_cached_embedding(texts[0])
            if cached is not None:
                return cached

        async with self._lock:
            # 异步执行CPU密集型任务
            loop = asyncio.get_event_loop()
            embeddings = await loop.run_in_executor(
                None,
                self._encode_sync,
                texts,
                normalize
            )

        # 缓存结果
        if use_cache and len(texts) == 1:
            await self._cache_embedding(texts[0], embeddings[0])

        return embeddings

    def _encode_sync(
        self,
        texts: List[str],
        normalize: bool
    ) -> np.ndarray:
        """同步编码（在线程池中执行）"""
        if self.model is None:
            raise RuntimeError("Model not loaded")

        embeddings = self.model.encode(
            texts,
            batch_size=self.batch_size,
            normalize_embeddings=normalize,
            convert_to_numpy=True,
            show_progress_bar=False
        )
        return embeddings

    async def _get_cached_embedding(self, text: str) -> Optional[np.ndarray]:
        """获取缓存的Embedding"""
        key = self._make_cache_key(text)
        cached = await self.cache.get(key)
        if cached is not None:
            return np.array(cached)
        return None

    async def _cache_embedding(self, text: str, embedding: np.ndarray):
        """缓存Embedding"""
        key = self._make_cache_key(text)
        await self.cache.set(key, embedding.tolist())

    def _make_cache_key(self, text: str) -> str:
        """生成缓存key"""
        text_hash = hashlib.md5(text.encode()).hexdigest()
        return f"emb:{self.model_name}:{text_hash}"

    def encode_sync(self, texts: List[str]) -> np.ndarray:
        """同步编码接口"""
        return self._encode_sync(texts, normalize=True)


class EmbeddingPool:
    """
    Embedding连接池
    支持多实例并发处理
    """

    def __init__(self, pool_size: int = 2):
        self.pool_size = pool_size
        self.instances: List[EmbeddingService] = []
        self._current = 0
        self._lock = asyncio.Lock()

    async def initialize(self):
        """初始化连接池"""
        logger.info(f"Initializing embedding pool (size={self.pool_size})")
        for i in range(self.pool_size):
            instance = EmbeddingService()
            self.instances.append(instance)
            logger.info(f"Instance {i+1}/{self.pool_size} ready")

    async def encode(self, texts: List[str]) -> np.ndarray:
        """轮询使用池中的实例"""
        async with self._lock:
            instance = self.instances[self._current]
            self._current = (self._current + 1) % len(self.instances)

        return await instance.encode(texts)

    async def close(self):
        """关闭连接池"""
        self.instances.clear()


# 全局服务实例
_embedding_service: Optional[EmbeddingService] = None


async def get_embedding_service() -> EmbeddingService:
    """获取全局Embedding服务实例"""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
        await _embedding_service.initialize()
    elif not _embedding_service._initialized:
        await _embedding_service.initialize()
    return _embedding_service


def get_embedding_service_sync() -> Optional[EmbeddingService]:
    """同步获取Embedding服务（仅用于已初始化场景）"""
    global _embedding_service
    return _embedding_service
