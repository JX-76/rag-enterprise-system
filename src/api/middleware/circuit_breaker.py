"""
Circuit Breaker Middleware - 熔断中间件
防止级联故障，自动熔断和恢复
"""
import time
import asyncio
from enum import Enum
from typing import Optional, Callable, Any
from dataclasses import dataclass
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from src.core.logging import get_logger

logger = get_logger(__name__)


class CircuitState(Enum):
    """熔断器状态"""
    CLOSED = "closed"      # 正常，请求通过
    OPEN = "open"          # 熔断，请求拒绝
    HALF_OPEN = "half_open"  # 半开，试探请求


@dataclass
class CircuitBreakerConfig:
    """熔断器配置"""
    failure_threshold: int = 5        # 触发熔断的失败次数
    recovery_timeout: float = 30.0    # 熔断后恢复等待时间（秒）
    half_open_max_calls: int = 3      # 半开状态最大试探请求数
    success_threshold: int = 2        # 半开状态成功次数，达到后关闭


class CircuitBreaker:
    """
    熔断器实现
    
    状态转换：
    CLOSED -> OPEN: 失败次数达到阈值
    OPEN -> HALF_OPEN: 经过recovery_timeout时间
    HALF_OPEN -> CLOSED: 成功次数达到阈值
    HALF_OPEN -> OPEN: 任何一次失败
    """
    
    def __init__(self, name: str, config: Optional[CircuitBreakerConfig] = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._half_open_calls = 0
        self._last_failure_time: Optional[float] = None
        self._lock = asyncio.Lock()
    
    @property
    def state(self) -> CircuitState:
        return self._state
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """执行被保护的函数"""
        async with self._lock:
            # 检查状态
            if self._state == CircuitState.OPEN:
                # 检查是否可以尝试恢复
                if self._can_attempt_reset():
                    self._state = CircuitState.HALF_OPEN
                    self._half_open_calls = 0
                    self._success_count = 0
                    logger.info(f"Circuit breaker '{self.name}' entering HALF_OPEN state")
                else:
                    raise CircuitBreakerOpen(
                        f"Circuit breaker '{self.name}' is OPEN"
                    )
            
            elif self._state == CircuitState.HALF_OPEN:
                if self._half_open_calls >= self.config.half_open_max_calls:
                    raise CircuitBreakerOpen(
                        f"Circuit breaker '{self.name}' half-open limit reached"
                    )
                self._half_open_calls += 1
        
        # 执行实际调用
        try:
            result = await func(*args, **kwargs)
            await self._on_success()
            return result
        except Exception as e:
            await self._on_failure()
            raise
    
    def _can_attempt_reset(self) -> bool:
        """检查是否可以尝试恢复"""
        if self._last_failure_time is None:
            return True
        return time.time() - self._last_failure_time >= self.config.recovery_timeout
    
    async def _on_success(self):
        """成功处理"""
        async with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.config.success_threshold:
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                    logger.info(f"Circuit breaker '{self.name}' CLOSED (recovered)")
            else:
                self._failure_count = 0
    
    async def _on_failure(self):
        """失败处理"""
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()
            
            if self._state == CircuitState.HALF_OPEN:
                # 半开状态失败，重新熔断
                self._state = CircuitState.OPEN
                logger.warning(
                    f"Circuit breaker '{self.name}' OPEN (half-open failed)"
                )
            elif self._failure_count >= self.config.failure_threshold:
                # 达到失败阈值，触发熔断
                self._state = CircuitState.OPEN
                logger.warning(
                    f"Circuit breaker '{self.name}' OPEN "
                    f"({self._failure_count} failures)"
                )


class CircuitBreakerMiddleware(BaseHTTPMiddleware):
    """熔断中间件"""
    
    def __init__(
        self,
        app: ASGIApp,
        config: Optional[CircuitBreakerConfig] = None
    ):
        super().__init__(app)
        self.config = config or CircuitBreakerConfig()
        self._breakers: dict[str, CircuitBreaker] = {}
        
        # 为不同服务创建熔断器
        self._services = [
            "embedding",
            "rerank",
            "llm",
            "vector_store"
        ]
        
        for service in self._services:
            self._breakers[service] = CircuitBreaker(service, self.config)
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """处理请求"""
        # 检查关键服务熔断状态
        open_services = [
            name for name, cb in self._breakers.items()
            if cb.state == CircuitState.OPEN
        ]
        
        if open_services:
            logger.warning(f"Services currently open: {open_services}")
        
        try:
            response = await call_next(request)
            return response
        except Exception as e:
            logger.error(f"Request failed: {e}")
            raise


class CircuitBreakerOpen(Exception):
    """熔断器打开异常"""
    pass


def circuit_breaker(
    name: str,
    failure_threshold: int = 5,
    recovery_timeout: float = 30.0
):
    """
    熔断装饰器
    
    Args:
        name: 熔断器名称
        failure_threshold: 失败阈值
        recovery_timeout: 恢复超时（秒）
    """
    breaker = CircuitBreaker(name, CircuitBreakerConfig(
        failure_threshold=failure_threshold,
        recovery_timeout=recovery_timeout
    ))
    
    def decorator(func):
        async def wrapper(*args, **kwargs):
            return await breaker.call(func, *args, **kwargs)
        
        # 附加熔断器实例，便于外部检查状态
        wrapper._circuit_breaker = breaker
        return wrapper
    
    return decorator
