"""
Circuit Breaker Middleware - 熔断中间件
防止级联故障，自动熔断和恢复
"""
import time
import asyncio
from enum import Enum
from typing import Optional, Callable, Any
from dataclasses import dataclass

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


class CircuitBreakerOpen(Exception):
    """熔断器打开异常"""
    pass


class CircuitBreaker:
    """
    熔断器实现
    
    状态转换：
    CLOSED -> OPEN: 失败次数达到阈值
    OPEN -> HALF_OPEN: 经过recovery_timeout时间
    HALF_OPEN -> CLOSED: 成功次数达到阈值
    HALF_OPEN -> OPEN: 任何一次失败
    
    使用示例：
        breaker = CircuitBreaker("vector_db", CircuitBreakerConfig())
        try:
            result = await breaker.call(database_query, param)
        except CircuitBreakerOpen:
            # 熔断时的降级处理
            return cached_result
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
        """
        执行受保护的操作
        
        Args:
            func: 要执行的异步函数
            *args, **kwargs: 函数参数
            
        Returns:
            函数执行结果
            
        Raises:
            CircuitBreakerOpen: 熔断器打开时
            Exception: 原函数抛出的异常
        """
        async with self._lock:
            await self._transition_state()
            
            if self._state == CircuitState.OPEN:
                raise CircuitBreakerOpen(
                    f"Circuit {self.name} is OPEN. "
                    f"Retry after {self.config.recovery_timeout}s"
                )
            
            if self._state == CircuitState.HALF_OPEN:
                if self._half_open_calls >= self.config.half_open_max_calls:
                    raise CircuitBreakerOpen(
                        f"Circuit {self.name} HALF_OPEN limit reached"
                    )
                self._half_open_calls += 1
        
        # 执行实际调用（在锁外执行，避免阻塞其他请求）
        try:
            result = await func(*args, **kwargs)
            await self._on_success()
            return result
        except Exception as e:
            await self._on_failure()
            raise
    
    async def _transition_state(self):
        """状态转换逻辑"""
        if self._state == CircuitState.OPEN:
            # 检查是否可以进入半开状态
            elapsed = time.time() - (self._last_failure_time or 0)
            if elapsed >= self.config.recovery_timeout:
                self._state = CircuitState.HALF_OPEN
                self._half_open_calls = 0
                self._success_count = 0
                logger.info(f"Circuit {self.name} entering HALF_OPEN")
    
    async def _on_failure(self):
        """失败处理"""
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()
            
            if self._state == CircuitState.HALF_OPEN:
                # 半开状态失败：回到熔断
                self._state = CircuitState.OPEN
                logger.warning(f"Circuit {self.name} back to OPEN due to failure in HALF_OPEN")
            elif self._failure_count >= self.config.failure_threshold:
                # 达到阈值：触发熔断
                self._state = CircuitState.OPEN
                logger.error(f"Circuit {self.name} OPENED after {self._failure_count} failures")
    
    async def _on_success(self):
        """成功处理"""
        async with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.config.success_threshold:
                    # 恢复成功：关闭熔断
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                    self._half_open_calls = 0
                    logger.info(f"Circuit {self.name} CLOSED (recovered)")
            else:
                # CLOSED状态下，重置失败计数
                if self._failure_count > 0:
                    self._failure_count = 0
    
    def get_metrics(self) -> dict:
        """获取熔断器指标"""
        return {
            "name": self.name,
            "state": self._state.value,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "half_open_calls": self._half_open_calls,
            "last_failure_time": self._last_failure_time
        }


class CircuitBreakerRegistry:
    """熔断器注册表"""
    
    def __init__(self):
        self._breakers: dict[str, CircuitBreaker] = {}
    
    def get_or_create(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None
    ) -> CircuitBreaker:
        """获取或创建熔断器"""
        if name not in self._breakers:
            self._breakers[name] = CircuitBreaker(name, config)
        return self._breakers[name]
    
    def get(self, name: str) -> Optional[CircuitBreaker]:
        """获取熔断器"""
        return self._breakers.get(name)
    
    def get_all_metrics(self) -> list:
        """获取所有熔断器指标"""
        return [breaker.get_metrics() for breaker in self._breakers.values()]


# 全局注册表
_registry = CircuitBreakerRegistry()


def get_circuit_breaker(
    name: str,
    config: Optional[CircuitBreakerConfig] = None
) -> CircuitBreaker:
    """获取熔断器"""
    return _registry.get_or_create(name, config)


def get_all_circuit_breaker_metrics() -> list:
    """获取所有熔断器指标"""
    return _registry.get_all_metrics()
