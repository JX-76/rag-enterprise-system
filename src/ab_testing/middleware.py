"""
A/B Test Middleware - A/B测试中间件
自动分配实验变体
"""
from typing import Optional
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from src.core.logging import get_logger
from src.ab_testing.manager import get_ab_test_manager

logger = get_logger(__name__)


class ABTestMiddleware(BaseHTTPMiddleware):
    """A/B测试中间件"""
    
    def __init__(
        self,
        app: ASGIApp,
        user_id_header: str = "X-User-ID",
        experiment_id: Optional[str] = None
    ):
        super().__init__(app)
        self.user_id_header = user_id_header
        self.experiment_id = experiment_id
    
    async def dispatch(self, request: Request, call_next):
        """处理请求"""
        if not self.experiment_id:
            return await call_next(request)
        
        # 获取用户ID
        user_id = request.headers.get(self.user_id_header, "anonymous")
        
        # 获取A/B测试管理器
        ab_manager = await get_ab_test_manager()
        
        # 分配变体
        variant = await ab_manager.get_variant(self.experiment_id, user_id)
        
        if variant:
            # 将变体信息存入请求状态
            request.state.ab_variant = variant
            request.state.ab_variant_id = variant.id
            request.state.ab_experiment_id = self.experiment_id
            
            logger.debug(f"Assigned variant {variant.name} to user {user_id}")
        
        response = await call_next(request)
        
        # 添加响应头
        if variant:
            response.headers["X-AB-Variant"] = variant.id
        
        return response


def get_current_variant(request) -> Optional[dict]:
    """获取当前请求的A/B测试变体"""
    variant = getattr(request.state, "ab_variant", None)
    if variant:
        return {
            "id": variant.id,
            "name": variant.name,
            "config": variant.config
        }
    return None
