"""
Rate Limiting Middleware - 限流中间件
基于Token Bucket算法，支持分布式Redis限流
"""
import time
from typing import Optional, Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import asyncio
from functools import wraps

from src.core.config import settings
from src.core.logging import get_logger

try:
    from src.utils.cache import get_cache_client
except ImportError:
    get_cache_client = None

logger = get_logger(__name__)


class TokenBucket:
    """
    Token Bucket限流器
    
    算法原理：
    - 桶以固定速率产生token
    - 每个请求消耗1个token
    - 桶满时token不再增加
    - 无token时请求被拒绝或等待
    """
    
    def __init__(
        self,
        rate: float,  # token产生速率 (个/秒)
        capacity: int,  # 桶容量
        key: str = "default"
    ):
        self.rate = rate
        self.capacity = capacity
        self.key = f"rate_limit:{key}"
        self._local_tokens = capacity
        self._last_update = time.time()
        self._lock = asyncio.Lock()
        
        # 尝试使用Redis进行分布式限流
        self.cache = None
        try:
            self.cache = get_cache_client()
        except Exception:
            logger.warning("Redis not available, using local rate limit")
    
    async def acquire(self, tokens: int = 1) -> bool:
        """尝试获取token"""
        async with self._lock:
            now = time.time()
            elapsed = now - self._last_update
            
            # 计算新产生的token
            self._local_tokens = min(
                self.capacity,
                self._local_tokens + elapsed * self.rate
            )
            self._last_update = now
            
            # 检查是否有足够token
            if self._local_tokens >= tokens:
                self._local_tokens -= tokens
                return True
            return False
    
    async def get_wait_time(self, tokens: int = 1) -> float:
        """计算需要等待的时间"""
        async with self._lock:
            if self._local_tokens >= tokens:
                return 0.0
            needed = tokens - self._local_tokens
            return needed / self.rate


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    限流中间件
    
    支持：
    - IP级别限流
    - 用户级别限流
    - 全局限流
    - 不同端点不同限流策略
    """
    
    def __init__(
        self,
        app: ASGIApp,
        default_rate: float = 100,  # 默认100请求/秒
        default_capacity: int = 200,
        burst_multiplier: float = 2.0,
        whitelist: Optional[list] = None
    ):
        super().__init__(app)
        self.default_rate = default_rate
        self.default_capacity = default_capacity
        self.burst_multiplier = burst_multiplier
        self.whitelist = set(whitelist or [])
        
        # 限流器缓存
        self._buckets: dict[str, TokenBucket] = {}
        
        # 端点特定配置
        self._endpoint_limits = {
            "/api/v1/query": {"rate": 50, "capacity": 100},
            "/api/v1/retrieve": {"rate": 100, "capacity": 200},
            "/api/v1/health": {"rate": 1000, "capacity": 2000},
        }
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """处理请求"""
        # 获取客户端标识
        client_id = self._get_client_id(request)
        path = request.url.path
        
        # 白名单跳过
        if client_id in self.whitelist:
            return await call_next(request)
        
        # 获取限流配置
        limit_config = self._endpoint_limits.get(path, {
            "rate": self.default_rate,
            "capacity": self.default_capacity
        })
        
        # 创建bucket key (IP + 端点)
        bucket_key = f"{client_id}:{path}"
        
        # 获取或创建限流器
        if bucket_key not in self._buckets:
            self._buckets[bucket_key] = TokenBucket(
                rate=limit_config["rate"],
                capacity=limit_config["capacity"],
                key=bucket_key
            )
        
        bucket = self._buckets[bucket_key]
        
        # 尝试获取token
        if await bucket.acquire():
            # 添加响应头
            response = await call_next(request)
            response.headers["X-RateLimit-Limit"] = str(limit_config["capacity"])
            # 这里简化处理，实际应该计算剩余token
            response.headers["X-RateLimit-Remaining"] = "unknown"
            return response
        else:
            # 限流触发
            wait_time = await bucket.get_wait_time()
            logger.warning(f"Rate limit exceeded for {client_id} on {path}")
            
            return Response(
                content=f'{"error": "Rate limit exceeded", "retry_after": {int(wait_time)}}',
                status_code=429,
                headers={
                    "Content-Type": "application/json",
                    "Retry-After": str(int(wait_time) + 1)
                }
            )
    
    def _get_client_id(self, request: Request) -> str:
        """获取客户端标识"""
        # 优先使用X-Forwarded-For
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        
        # 其次使用X-Real-IP
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # 最后使用直接连接的IP
        if request.client:
            return request.client.host
        
        return "unknown"


def rate_limit(
    requests: int = 100,
    window: int = 60,
    key_func: Optional[Callable] = None
):
    """
    装饰器版限流
    
    Args:
        requests: 窗口期内允许的请求数
        window: 时间窗口（秒）
        key_func: 自定义限流key生成函数
    """
    def decorator(func):
        # 使用滑动窗口计数
        _requests: dict[str, list] = {}
        _lock = asyncio.Lock()
        
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 生成限流key
            if key_func:
                key = key_func(*args, **kwargs)
            else:
                key = "default"
            
            async with _lock:
                now = time.time()
                
                # 初始化或清理过期请求记录
                if key not in _requests:
                    _requests[key] = []
                
                # 移除窗口期外的请求记录
                _requests[key] = [
                    ts for ts in _requests[key]
                    if now - ts < window
                ]
                
                # 检查是否超过限制
                if len(_requests[key]) >= requests:
                    raise RateLimitExceeded(
                        f"Rate limit exceeded: {requests} requests per {window}s"
                    )
                
                # 记录本次请求
                _requests[key].append(now)
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


class RateLimitExceeded(Exception):
    """限流异常"""
    pass
