"""
Enterprise RAG System - Main Entry Point
工业级RAG系统主入口
"""
import asyncio
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import time
import uuid

from src.api.routes import retrieval, query, health
from src.core.config import settings
from src.core.logging import setup_logging, get_logger
from src.core.monitoring import metrics
from src.utils.cache import CacheManager

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动
    logger.info("Starting Enterprise RAG System...")
    app.state.cache = CacheManager()
    app.state.start_time = time.time()
    logger.info("✓ Cache initialized")
    
    yield
    
    # 关闭
    logger.info("Shutting down Enterprise RAG System...")
    await app.state.cache.close()
    logger.info("✓ Cache closed")


app = FastAPI(
    title="Enterprise RAG System",
    description="工业级检索增强生成系统",
    version="1.0.0",
    lifespan=lifespan
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_request_metadata(request: Request, call_next):
    """添加请求元数据（TraceID、耗时等）"""
    start_time = time.time()
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    
    # 记录请求
    logger.info(f"[{request_id}] {request.method} {request.url.path}")
    
    response = await call_next(request)
    
    # 计算耗时
    process_time = (time.time() - start_time) * 1000
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time"] = f"{process_time:.2f}ms"
    
    # 记录指标
    metrics.record_request(request.url.path, response.status_code, process_time)
    
    logger.info(f"[{request_id}] Completed in {process_time:.2f}ms")
    
    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """全局异常处理"""
    request_id = getattr(request.state, 'request_id', 'unknown')
    logger.error(f"[{request_id}] Unhandled exception: {exc}", exc_info=True)
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "request_id": request_id
        }
    )


# 注册路由
app.include_router(health.router, prefix="/health", tags=["Health"])
app.include_router(retrieval.router, prefix="/api/v1/retrieve", tags=["Retrieval"])
app.include_router(query.router, prefix="/api/v1/query", tags=["Query"])


if __name__ == "__main__":
    setup_logging()
    uvicorn.run(
        "src.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        workers=1 if settings.DEBUG else settings.WORKERS
    )
