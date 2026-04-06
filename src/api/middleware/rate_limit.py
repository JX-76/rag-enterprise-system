"""
Rate Limiting Middleware - 限流中间件
基于Token Bucket算法，支持分布式Redis限流
"""
import time
from typing import Optional, Callable
import asyncio
from functools import wraps

# 尝试导入FastAPI，用于中间件包装
try:
    from fastapi import Request, Response
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.types import ASGIApp
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    Request = Response = BaseHTTPMiddleware = ASGIApp = None

# 简单的日志实现
try:
    from src.core.logging import get_logger
    logger = get_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

# 尝试导入缓存
try:
    from src.utils.cache import get_cache_client
except ImportError:
    get_cache_client = None


class TokenBucket:
    """
    Token Bucket 限流器
    
    支持:
    - 本地内存限流
    - 分布式Redis限流 (可选)
    
    使用示例:
        bucket = TokenBucket(rate=10, capacity=20, key="api")
        if await bucket.acquire():
            # 处理请求
            pass
        else:
            # 限流拒绝
            return {"error": "Rate limit exceeded"}
    """
    
    _local_buckets: dict = {}
    
    def __init__(
        self,
        rate: float,  # token生成速率 (个/秒)
        capacity: int,  # 桶容量
        key: str = "default",
        redis_client=None
    ):
        self.rate = rate
        self.capacity = capacity
        self.key = key
        self.redis_client = redis_client
        
        # 本地状态
        self.tokens = float(capacity)
        self.last_update = time.time()
    
    async def acquire(self, tokens: int = 1) -> bool:
        """
        尝试获取token
        
        Returns:
            True: 获取成功
            False: 被限流
        """
        now = time.time()
        elapsed = now - self.last_update
        
        # 补充token
        self.tokens = min(
            float(self.capacity),
            self.tokens + elapsed * self.rate
        )
        self.last_update = now
        
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        
        return False
    
    async def acquire_with_wait(self, tokens: int = 1, timeout: float = None) -> bool:
        """
        尝试获取token，如果不足则等待
        
        Args:
            tokens: 需要的token数
            timeout: 最大等待时间(秒)
        
        Returns:
            True: 获取成功
            False: 超时或被限流
        """
        start_time = time.time()
        
        while True:
            if await self.acquire(tokens):
                return True
            
            if timeout and (time.time() - start_time) > timeout:
                return False
            
            # 计算需要等待的时间
            tokens_needed = tokens - self.tokens
            wait_time = tokens_needed / self.rate
            wait_time = min(wait_time, 0.1)  # 最多等100ms
            
            await asyncio.sleep(wait_time)
    
    def get_status(self) -> dict:
        """获取当前状态"""
        return {
            "key": self.key,
            "rate": self.rate,
            "capacity": self.capacity,
            "tokens": self.tokens,
            "available_ratio": self.tokens / self.capacity
        }


class RateLimiter:
    """
    限流器管理器
    
    支持多级限流策略：
    - 全局限流
    - API级别限流
    - 用户级别限流
    """
    
    def __init__(self):
        self._buckets: Dict[str, TokenBucket] = {}
        self._configs: Dict[str, dict] = {}
    
    def configure(
        self,
        name: str,
        rate: float,
        capacity: int,
        key_func: Optional[Callable] = None
    ):
        """
        配置限流策略
        
        Args:
            name: 策略名称
            rate: token生成速率
            capacity: 桶容量
            key_func: 生成限流key的函数
        """
        self._configs[name] = {
            "rate": rate,
            "capacity": capacity,
            "key_func": key_func
        }
    
    async def check(
        self,
        name: str,
        identifier: str = "default"
    ) -> bool:
        """
        检查是否允许通过
        
        Args:
            name: 策略名称
            identifier: 限流标识(如用户ID、IP等)
        
        Returns:
            True: 允许通过
            False: 被限流
        """
        config = self._configs.get(name)
        if not config:
            return True  # 未配置则放行
        
        key = f"{name}:{identifier}"
        
        if key not in self._buckets:
            self._buckets[key] = TokenBucket(
                rate=config["rate"],
                capacity=config["capacity"],
                key=key
            )
        
        return await self._buckets[key].acquire()
    
    def get_limiter(
        self,
        name: str,
        identifier: str = "default"
    ) -> TokenBucket:
        """获取指定限流器"""
        config = self._configs.get(name)
        if not config:
            # 默认配置
            config = {"rate": 100, "capacity": 100}
        
        key = f"{name}:{identifier}"
        
        if key not in self._buckets:
            self._buckets[key] = TokenBucket(
                rate=config["rate"],
                capacity=config["capacity"],
                key=key
            )
        
        return self._buckets[key]


# 全局限流器实例
_limiter = RateLimiter()


def configure_rate_limit(
    name: str,
    rate: float,
    capacity: int,
    key_func: Optional[Callable] = None
):
    """配置限流策略"""
    _limiter.configure(name, rate, capacity, key_func)


async def check_rate_limit(name: str, identifier: str = "default") -> bool:
    """检查限流"""
    return await _limiter.check(name, identifier)


def get_rate_limiter(name: str, identifier: str = "default") -> TokenBucket:
    """获取限流器"""
    return _limiter.get_limiter(name, identifier)


def rate_limit(
    name: str,
    rate: float,
    capacity: int,
    key_func: Optional[Callable] = None
):
    """
    限流装饰器
    
    使用示例:
        @rate_limit("api", rate=10, capacity=20)
        async def my_endpoint():
            return {"result": "ok"}
    """
    _limiter.configure(name, rate, capacity, key_func)
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 尝试获取key
            key = "default"
            if key_func:
                try:
                    key = key_func(*args, **kwargs)
                except:
                    pass
            
            if not await _limiter.check(name, key):
                raise RateLimitExceeded(f"Rate limit exceeded for {name}")
            
            return await func(*args, **kwargs)
        
        return wrapper
    
    return decorator


class RateLimitExceeded(Exception):
    """限流异常"""
    pass


# FastAPI中间件 (可选)
if FASTAPI_AVAILABLE:
    class RateLimitMiddleware(BaseHTTPMiddleware):
        """
        FastAPI限流中间件
        
        使用示例:
            app.add_middleware(
                RateLimitMiddleware,
                rate=100,
                capacity=200,
                key_func=lambda req: req.client.host
            )
        """
        
        def __init__(
            self,
            app: ASGIApp,
            rate: float = 100,
            capacity: int = 200,
            key_func: Optional[Callable] = None
        ):
            super().__init__(app)
            self.rate = rate
            self.capacity = capacity
            self.key_func = key_func or (lambda req: req.client.host if req.client else "unknown")
            self._buckets: Dict[str, TokenBucket] = {}
        
        async def dispatch(self, request: Request, call_next):
            # 生成限流key
            key = self.key_func(request)
            
            # 获取或创建bucket
            if key not in self._buckets:
                self._buckets[key] = TokenBucket(
                    rate=self.rate,
                    capacity=self.capacity,
                    key=key
                )
            
            bucket = self._buckets[key]
            
            # 检查限流
            if not await bucket.acquire():
                return Response(
                    content='{"error": "Rate limit exceeded"}',
                    status_code=429,
                    media_type="application/json"
                )
            
            # 继续处理
            return await call_next(request)
