"""
Cache Manager - 缓存管理
支持本地LRU缓存和Redis分布式缓存，带连接池和降级策略
"""
from typing import Optional, Any, Dict
import hashlib
import json
import asyncio
from collections import OrderedDict
import time

try:
    from functools import lru_cache
except ImportError:
    from functools import cache as lru_cache

from src.core.config import settings
from src.core.logging import get_logger

logger = get_logger(__name__)


class LocalLRUCache:
    """本地LRU缓存（Redis降级用）"""
    
    def __init__(self, capacity: int = 1000, default_ttl: int = 3600):
        self.capacity = capacity
        self.default_ttl = default_ttl
        self.cache: OrderedDict[str, Any] = OrderedDict()
        self.expiry: Dict[str, float] = {}
        self._lock = asyncio.Lock()
    
    async def get(self, key: str) -> Optional[Any]:
        """获取缓存"""
        async with self._lock:
            # 检查是否过期
            if key in self.expiry and time.time() > self.expiry[key]:
                self.cache.pop(key, None)
                self.expiry.pop(key, None)
                return None
            
            if key in self.cache:
                # 移到末尾（最近使用）
                self.cache.move_to_end(key)
                return self.cache[key]
            return None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """设置缓存"""
        async with self._lock:
            ttl = ttl or self.default_ttl
            
            # 如果满，移除最旧的
            if len(self.cache) >= self.capacity and key not in self.cache:
                oldest = next(iter(self.cache))
                self.cache.pop(oldest)
                self.expiry.pop(oldest, None)
            
            self.cache[key] = value
            self.cache.move_to_end(key)
            self.expiry[key] = time.time() + ttl
    
    async def delete(self, key: str) -> None:
        """删除缓存"""
        async with self._lock:
            self.cache.pop(key, None)
            self.expiry.pop(key, None)
    
    async def clear(self) -> None:
        """清空缓存"""
        async with self._lock:
            self.cache.clear()
            self.expiry.clear()


class RedisConnectionPool:
    """Redis连接池管理"""
    
    def __init__(self, max_connections: int = 20, socket_timeout: int = 5):
        self.redis_url = settings.REDIS_URL
        self.max_connections = max_connections
        self.socket_timeout = socket_timeout
        self._pool = None
        self._client = None
        self._available = True
    
    async def initialize(self):
        """初始化连接池"""
        if not self.redis_url:
            logger.info("Redis URL not configured, skipping pool initialization")
            return
        
        try:
            import redis.asyncio as redis
            
            self._pool = redis.ConnectionPool.from_url(
                self.redis_url,
                max_connections=self.max_connections,
                socket_connect_timeout=self.socket_timeout,
                socket_timeout=self.socket_timeout,
                retry_on_timeout=True,
                decode_responses=True
            )
            
            self._client = redis.Redis(connection_pool=self._pool)
            
            # 测试连接
            await self._client.ping()
            logger.info(f"Redis connection pool initialized (max={self.max_connections})")
            
        except Exception as e:
            logger.error(f"Failed to initialize Redis pool: {e}")
            self._available = False
            raise
    
    async def get_client(self):
        """获取Redis客户端"""
        if self._client and self._available:
            return self._client
        return None
    
    async def health_check(self) -> bool:
        """健康检查"""
        if not self._client or not self._available:
            return False
        try:
            await self._client.ping()
            return True
        except Exception:
            self._available = False
            return False
    
    async def close(self):
        """关闭连接池"""
        if self._pool:
            await self._pool.disconnect()
            logger.info("Redis connection pool closed")


class CacheManager:
    """
    缓存管理器（带降级策略）
    
    降级策略：
    1. Redis可用 -> 使用Redis
    2. Redis不可用 -> 降级到本地LRU缓存
    3. 两者都失败 -> 返回None（无缓存）
    """
    
    def __init__(self):
        self.redis_pool = None
        self.local_cache = LocalLRUCache(capacity=10000, default_ttl=3600)
        self.redis_available = False
        self._circuit_failures = 0
        self._circuit_threshold = 5
        self._circuit_open = False
        self._circuit_reset_time = 0
    
    async def initialize(self):
        """初始化缓存管理器"""
        if settings.REDIS_URL:
            try:
                self.redis_pool = RedisConnectionPool()
                await self.redis_pool.initialize()
                self.redis_available = True
            except Exception as e:
                logger.warning(f"Redis unavailable, using local cache: {e}")
                self.redis_available = False
    
    async def _is_circuit_open(self) -> bool:
        """检查熔断器状态"""
        if not self._circuit_open:
            return False
        
        # 检查是否应该尝试恢复
        if time.time() > self._circuit_reset_time:
            self._circuit_open = False
            self._circuit_failures = 0
            logger.info("Cache circuit breaker reset, trying Redis again")
            return False
        
        return True
    
    async def get(self, key: str) -> Optional[Any]:
        """获取缓存（带降级）"""
        # 尝试Redis
        if self.redis_available and not await self._is_circuit_open():
            try:
                client = await self.redis_pool.get_client()
                if client:
                    value = await client.get(key)
                    if value:
                        self._circuit_failures = 0  # 成功，重置失败计数
                        return json.loads(value)
            except Exception as e:
                self._circuit_failures += 1
                if self._circuit_failures >= self._circuit_threshold:
                    self._circuit_open = True
                    self._circuit_reset_time = time.time() + 30  # 30秒后重试
                    logger.warning(f"Cache circuit breaker opened: {e}")
        
        # 降级到本地缓存
        return await self.local_cache.get(key)
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """设置缓存（双写策略）"""
        ttl = ttl or 3600
        
        # 写入本地缓存（始终写入）
        await self.local_cache.set(key, value, ttl)
        
        # 尝试写入Redis
        if self.redis_available and not await self._is_circuit_open():
            try:
                client = await self.redis_pool.get_client()
                if client:
                    await client.setex(
                        key,
                        ttl,
                        json.dumps(value, default=str)
                    )
            except Exception as e:
                logger.debug(f"Redis write failed (using local cache): {e}")
    
    async def delete(self, key: str) -> None:
        """删除缓存"""
        # 删除本地缓存
        await self.local_cache.delete(key)
        
        # 尝试删除Redis
        if self.redis_available:
            try:
                client = await self.redis_pool.get_client()
                if client:
                    await client.delete(key)
            except Exception:
                pass
    
    async def close(self):
        """关闭连接"""
        if self.redis_pool:
            await self.redis_pool.close()
    
    @staticmethod
    def make_key(*args, **kwargs) -> str:
        """生成缓存key"""
        key_data = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True)
        return hashlib.md5(key_data.encode()).hexdigest()
    
    async def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        return {
            "redis_available": self.redis_available,
            "circuit_open": self._circuit_open,
            "circuit_failures": self._circuit_failures,
            "local_cache_size": len(self.local_cache.cache)
        }


# 全局实例
_cache_manager: Optional[CacheManager] = None


async def get_cache_manager() -> CacheManager:
    """获取全局缓存管理器"""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager()
        await _cache_manager.initialize()
    return _cache_manager


def get_cache_client():
    """获取缓存客户端（兼容旧接口）"""
    return None  # 新版使用get_cache_manager
