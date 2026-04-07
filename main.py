"""
RAG Demo - FastAPI入口
启动命令: python main.py
"""
import os
import sys
import logging
from contextlib import asynccontextmanager

# 添加src到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings, check_config
from src.api.routes import router, init_components

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动
    logger.info("=" * 50)
    logger.info(f"启动 {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info("=" * 50)
    
    # 检查配置
    check_config()
    
    # 初始化组件
    try:
        init_components()
        logger.info("✓ 组件初始化完成")
    except Exception as e:
        logger.error(f"✗ 组件初始化失败: {e}")
        logger.warning("部分功能可能不可用，请检查配置")
    
    yield
    
    # 关闭
    logger.info("正在关闭服务...")


# 创建FastAPI应用
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="基于LangChain+Milvus的大模型RAG问答Demo",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应限制域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(router)


@app.get("/")
async def root():
    """根路径"""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "health": "/api/v1/health"
    }


if __name__ == "__main__":
    import uvicorn
    
    logger.info(f"服务启动: http://{settings.HOST}:{settings.PORT}")
    logger.info(f"接口文档: http://{settings.HOST}:{settings.PORT}/docs")
    
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )
