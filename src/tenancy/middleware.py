"""
Tenant Middleware - 租户中间件
处理租户识别、API Key验证、配额检查
"""
from typing import Optional
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from src.core.logging import get_logger
from src.tenancy.manager import get_tenant_manager, Tenant

logger = get_logger(__name__)


class TenantMiddleware(BaseHTTPMiddleware):
    """
    租户中间件
    
    功能：
    1. 从请求中提取租户信息
    2. 验证API Key
    3. 检查配额和速率限制
    4. 将租户信息注入请求上下文
    """
    
    def __init__(
        self,
        app: ASGIApp,
        header_name: str = "X-API-Key",
        exclude_paths: Optional[list] = None
    ):
        super().__init__(app)
        self.header_name = header_name
        self.exclude_paths = exclude_paths or [
            "/health",
            "/docs",
            "/openapi.json",
            "/redoc"
        ]
    
    async def dispatch(self, request: Request, call_next):
        """处理请求"""
        path = request.url.path
        
        # 排除路径
        if any(path.startswith(excluded) for excluded in self.exclude_paths):
            return await call_next(request)
        
        # 获取API Key
        api_key = request.headers.get(self.header_name)
        
        if not api_key:
            logger.warning(f"Missing API Key for {path}")
            raise HTTPException(status_code=401, detail="Missing API Key")
        
        # 验证租户
        tenant_manager = await get_tenant_manager()
        tenant = await tenant_manager.get_tenant_by_api_key(api_key)
        
        if not tenant:
            logger.warning(f"Invalid API Key: {api_key[:10]}...")
            raise HTTPException(status_code=401, detail="Invalid API Key")
        
        if not tenant.is_active:
            logger.warning(f"Inactive tenant: {tenant.id}")
            raise HTTPException(status_code=403, detail="Tenant is inactive")
        
        # 检查速率限制
        if not await tenant_manager.check_rate_limit(tenant.id):
            logger.warning(f"Rate limit exceeded for tenant: {tenant.id}")
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
        
        # 将租户信息存入请求状态
        request.state.tenant = tenant
        request.state.tenant_id = tenant.id
        
        logger.debug(f"Request from tenant: {tenant.name} ({tenant.id})")
        
        # 继续处理请求
        response = await call_next(request)
        
        # 添加租户响应头
        response.headers["X-Tenant-ID"] = tenant.id
        
        return response


def get_current_tenant(request: Request) -> Optional[Tenant]:
    """获取当前请求的租户"""
    return getattr(request.state, "tenant", None)


def get_current_tenant_id(request: Request) -> Optional[str]:
    """获取当前请求的租户ID"""
    return getattr(request.state, "tenant_id", None)
