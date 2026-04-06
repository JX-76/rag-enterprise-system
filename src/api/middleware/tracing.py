"""
Tracing Middleware - 链路追踪中间件
支持TraceID全链路追踪
"""
import time
import uuid
from typing import Optional
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from contextvars import ContextVar

from src.core.logging import get_logger

logger = get_logger(__name__)

# 上下文变量，用于在异步调用中传递trace信息
trace_id_var: ContextVar[str] = ContextVar('trace_id', default='')
span_id_var: ContextVar[str] = ContextVar('span_id', default='')
parent_span_id_var: ContextVar[Optional[str]] = ContextVar('parent_span_id', default=None)


class TracingMiddleware(BaseHTTPMiddleware):
    """
    链路追踪中间件
    
    功能：
    - 生成/传播TraceID
    - 记录请求耗时
    - 结构化日志输出
    """
    
    def __init__(
        self,
        app: ASGIApp,
        header_name: str = "X-Request-ID",
        response_header: str = "X-Request-ID"
    ):
        super().__init__(app)
        self.header_name = header_name
        self.response_header = response_header
    
    async def dispatch(self, request: Request, call_next) -> Response:
        """处理请求"""
        # 获取或生成TraceID
        trace_id = request.headers.get(self.header_name)
        if not trace_id:
            trace_id = self._generate_trace_id()
        
        # 设置上下文
        trace_id_var.set(trace_id)
        span_id_var.set(self._generate_span_id())
        parent_span_id_var.set(None)
        
        # 存储到request state
        request.state.trace_id = trace_id
        request.state.request_id = trace_id
        
        # 记录开始时间
        start_time = time.time()
        
        # 记录请求信息
        logger.info(
            f"Request started: {request.method} {request.url.path}",
            extra={
                "trace_id": trace_id,
                "method": request.method,
                "path": request.url.path,
                "query_params": str(request.query_params),
                "client_host": request.client.host if request.client else None
            }
        )
        
        try:
            response = await call_next(request)
            
            # 计算耗时
            duration = time.time() - start_time
            
            # 添加响应头
            response.headers[self.response_header] = trace_id
            response.headers["X-Response-Time"] = f"{duration:.3f}s"
            
            # 记录响应
            logger.info(
                f"Request completed: {request.method} {request.url.path} - {response.status_code}",
                extra={
                    "trace_id": trace_id,
                    "status_code": response.status_code,
                    "duration_ms": duration * 1000
                }
            )
            
            return response
            
        except Exception as e:
            duration = time.time() - start_time
            
            logger.error(
                f"Request failed: {request.method} {request.url.path} - {str(e)}",
                extra={
                    "trace_id": trace_id,
                    "error": str(e),
                    "duration_ms": duration * 1000
                },
                exc_info=True
            )
            raise
    
    def _generate_trace_id(self) -> str:
        """生成TraceID"""
        return str(uuid.uuid4()).replace("-", "")
    
    def _generate_span_id(self) -> str:
        """生成SpanID"""
        return str(uuid.uuid4()).replace("-", "")[:16]


def get_current_trace_id() -> str:
    """获取当前请求的TraceID"""
    return trace_id_var.get()


def get_current_span_id() -> str:
    """获取当前SpanID"""
    return span_id_var.get()


class TracedFunction:
    """
    函数追踪装饰器
    用于追踪业务函数的执行
    """
    
    def __init__(self, name: Optional[str] = None):
        self.name = name
    
    def __call__(self, func):
        async def wrapper(*args, **kwargs):
            span_name = self.name or func.__name__
            start_time = time.time()
            
            trace_id = get_current_trace_id()
            parent_span = get_current_span_id()
            
            # 生成新span
            current_span = str(uuid.uuid4()).replace("-", "")[:16]
            span_id_var.set(current_span)
            parent_span_id_var.set(parent_span)
            
            logger.debug(
                f"Span started: {span_name}",
                extra={
                    "trace_id": trace_id,
                    "span_id": current_span,
                    "parent_span_id": parent_span,
                    "operation": span_name
                }
            )
            
            try:
                result = await func(*args, **kwargs)
                
                duration = time.time() - start_time
                logger.debug(
                    f"Span completed: {span_name}",
                    extra={
                        "trace_id": trace_id,
                        "span_id": current_span,
                        "operation": span_name,
                        "duration_ms": duration * 1000
                    }
                )
                
                return result
                
            except Exception as e:
                duration = time.time() - start_time
                logger.error(
                    f"Span failed: {span_name}",
                    extra={
                        "trace_id": trace_id,
                        "span_id": current_span,
                        "operation": span_name,
                        "duration_ms": duration * 1000,
                        "error": str(e)
                    }
                )
                raise
            finally:
                # 恢复父span
                span_id_var.set(parent_span)
        
        return wrapper


def traced(name: Optional[str] = None):
    """函数追踪装饰器快捷方式"""
    def decorator(func):
        tracer = TracedFunction(name)
        return tracer(func)
    return decorator
