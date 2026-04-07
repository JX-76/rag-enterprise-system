"""
性能优化模块

优化策略:
1. 向量检索缓存
2. 连接池管理
3. 批量操作优化
4. 异步处理支持
"""
import time
import hashlib
from functools import wraps
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass
from collections import OrderedDict
import logging

logger = logging.getLogger(__name__)


class LRUCache:
    """LRU缓存实现"""
    
    def __init__(self, max_size: int = 100, ttl: int = 300):
        """
        Args:
            max_size: 最大缓存条目数
            ttl: 缓存过期时间（秒）
        """
        self.max_size = max_size
        self.ttl = ttl
        self.cache: OrderedDict[str, Any] = OrderedDict()
        self.timestamps: Dict[str, float] = {}
    
    def _is_expired(self, key: str) -> bool:
        """检查是否过期"""
        if key not in self.timestamps:
            return True
        return time.time() - self.timestamps[key] > self.ttl
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        if key in self.cache:
            if self._is_expired(key):
                self.delete(key)
                return None
            # 移到末尾（最近使用）
            self.cache.move_to_end(key)
            return self.cache[key]
        return None
    
    def set(self, key: str, value: Any):
        """设置缓存值"""
        # 如果已存在，更新并移到末尾
        if key in self.cache:
            self.cache.move_to_end(key)
        # 如果已满，删除最旧的
        elif len(self.cache) >= self.max_size:
            oldest = next(iter(self.cache))
            self.delete(oldest)
        
        self.cache[key] = value
        self.timestamps[key] = time.time()
    
    def delete(self, key: str):
        """删除缓存"""
        self.cache.pop(key, None)
        self.timestamps.pop(key, None)
    
    def clear(self):
        """清空缓存"""
        self.cache.clear()
        self.timestamps.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        # 清理过期项
        expired = [k for k in self.timestamps if self._is_expired(k)]
        for k in expired:
            self.delete(k)
        
        return {
            "size": len(self.cache),
            "max_size": self.max_size,
            "ttl": self.ttl,
            "expired_cleaned": len(expired)
        }


class VectorSearchCache:
    """向量检索结果缓存"""
    
    def __init__(self, cache_size: int = 500, ttl: int = 600):
        self.cache = LRUCache(max_size=cache_size, ttl=ttl)
        self.hit_count = 0
        self.miss_count = 0
    
    def _make_key(self, query_embedding: List[float], top_k: int) -> str:
        """生成缓存键"""
        # 简化向量用于哈希
        simplified = [round(x, 4) for x in query_embedding[:10]]
        key_str = f"{simplified}_{top_k}"
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def get(self, query_embedding: List[float], top_k: int) -> Optional[List[Any]]:
        """获取缓存结果"""
        key = self._make_key(query_embedding, top_k)
        result = self.cache.get(key)
        
        if result is not None:
            self.hit_count += 1
            logger.debug(f"向量缓存命中: {key[:8]}")
        else:
            self.miss_count += 1
        
        return result
    
    def set(self, query_embedding: List[float], top_k: int, results: List[Any]):
        """缓存结果"""
        key = self._make_key(query_embedding, top_k)
        self.cache.set(key, results)
        logger.debug(f"向量缓存写入: {key[:8]}")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计"""
        total = self.hit_count + self.miss_count
        hit_rate = self.hit_count / total if total > 0 else 0
        
        return {
            **self.cache.get_stats(),
            "hit_count": self.hit_count,
            "miss_count": self.miss_count,
            "hit_rate": f"{hit_rate*100:.1f}%"
        }


def timed(func: Callable) -> Callable:
    """性能计时装饰器"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        elapsed = time.time() - start
        logger.info(f"{func.__name__} 耗时: {elapsed*1000:.2f}ms")
        return result
    return wrapper


class BatchProcessor:
    """批量处理优化器"""
    
    def __init__(self, batch_size: int = 32, max_workers: int = 4):
        self.batch_size = batch_size
        self.max_workers = max_workers
    
    def split_batches(self, items: List[Any]) -> List[List[Any]]:
        """分割为批次"""
        return [
            items[i:i + self.batch_size]
            for i in range(0, len(items), self.batch_size)
        ]
    
    def process_batch(
        self,
        items: List[Any],
        processor: Callable[[Any], Any]
    ) -> List[Any]:
        """顺序批量处理"""
        results = []
        for item in items:
            try:
                result = processor(item)
                results.append(result)
            except Exception as e:
                logger.error(f"处理失败: {e}")
                results.append(None)
        return results


@dataclass
class PerformanceMetrics:
    """性能指标"""
    query_count: int = 0
    total_time: float = 0.0
    cache_hits: int = 0
    cache_misses: int = 0
    
    @property
    def avg_query_time(self) -> float:
        if self.query_count == 0:
            return 0.0
        return self.total_time / self.query_count
    
    @property
    def cache_hit_rate(self) -> float:
        total = self.cache_hits + self.cache_misses
        if total == 0:
            return 0.0
        return self.cache_hits / total
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "query_count": self.query_count,
            "total_time": f"{self.total_time:.2f}s",
            "avg_query_time": f"{self.avg_query_time*1000:.2f}ms",
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "cache_hit_rate": f"{self.cache_hit_rate*100:.1f}%"
        }


class PerformanceMonitor:
    """性能监控器"""
    
    def __init__(self):
        self.metrics = PerformanceMetrics()
        self.query_times: List[float] = []
    
    def record_query(self, elapsed: float, cache_hit: bool = False):
        """记录查询"""
        self.metrics.query_count += 1
        self.metrics.total_time += elapsed
        self.query_times.append(elapsed)
        
        if cache_hit:
            self.metrics.cache_hits += 1
        else:
            self.metrics.cache_misses += 1
    
    def get_report(self) -> Dict[str, Any]:
        """获取性能报告"""
        if not self.query_times:
            return {"status": "no_data"}
        
        times = sorted(self.query_times)
        return {
            **self.metrics.to_dict(),
            "p50_latency": f"{times[len(times)//2]*1000:.2f}ms",
            "p95_latency": f"{times[int(len(times)*0.95)]*1000:.2f}ms",
            "p99_latency": f"{times[int(len(times)*0.99)]*1000:.2f}ms" if len(times) >= 100 else "N/A"
        }
    
    def reset(self):
        """重置统计"""
        self.metrics = PerformanceMetrics()
        self.query_times = []


# 全局性能优化实例
vector_cache = VectorSearchCache()
performance_monitor = PerformanceMonitor()


def get_optimizer_stats() -> Dict[str, Any]:
    """获取优化器统计"""
    return {
        "vector_cache": vector_cache.get_stats(),
        "performance": performance_monitor.get_report()
    }
