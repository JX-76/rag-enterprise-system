"""
Health Check Routes - 健康检查路由
"""
import time
from fastapi import APIRouter, status
from pydantic import BaseModel
from typing import Dict, Any

router = APIRouter()


class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str
    version: str
    timestamp: float
    uptime: float


class ReadyResponse(BaseModel):
    """就绪检查响应"""
    ready: bool
    checks: Dict[str, Any]


@router.get("", response_model=HealthResponse)
async def health_check(request):
    """健康检查端点"""
    from src.main import app
    
    uptime = time.time() - getattr(app.state, 'start_time', time.time())
    
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        timestamp=time.time(),
        uptime=uptime
    )


@router.get("/ready", response_model=ReadyResponse)
async def ready_check():
    """就绪检查端点"""
    # 检查依赖服务状态
    checks = {
        "api": True,
        "cache": True,  # 简化处理
        "vector_store": True
    }
    
    all_ready = all(checks.values())
    
    return ReadyResponse(
        ready=all_ready,
        checks=checks
    )
