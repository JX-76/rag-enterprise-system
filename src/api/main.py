"""
FastAPI 主应用
企业级API入口，集成所有模块
"""
import time
from typing import List, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# 导入配置
from src.config import settings

# 导入核心模块
from src.api.middleware.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
from src.api.middleware.rate_limit import TokenBucket
from src.ingestion.document_parser import DocumentParser
from src.ingestion.parent_child_chunker import ParentChildChunker
from src.rag.query_rewriter import QueryRewriter

# 尝试导入监控
try:
    from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
    PROMETHEUS_AVAILABLE = True
    
    # 定义指标
    REQUEST_COUNT = Counter('rag_requests_total', 'Total requests', ['method', 'endpoint'])
    REQUEST_LATENCY = Histogram('rag_request_duration_seconds', 'Request latency')
    RETRIEVAL_LATENCY = Histogram('rag_retrieval_duration_seconds', 'Retrieval latency')
except ImportError:
    PROMETHEUS_AVAILABLE = False


# ========== Pydantic Models ==========

class HealthCheck(BaseModel):
    status: str
    version: str
    timestamp: float


class IngestRequest(BaseModel):
    content: str = Field(..., description="文档内容")
    metadata: Optional[dict] = Field(default=None, description="文档元数据")
    chunking_strategy: str = Field(default="parent_child", description="分块策略")


class IngestResponse(BaseModel):
    success: bool
    num_chunks: int
    chunk_ids: List[str]
    message: str


class QueryRequest(BaseModel):
    query: str = Field(..., description="用户查询")
    top_k: int = Field(default=5, ge=1, le=20)
    enable_rewrite: bool = Field(default=True)
    return_sources: bool = Field(default=True)


class Source(BaseModel):
    content: str
    score: float
    metadata: Optional[dict] = None


class QueryResponse(BaseModel):
    query: str
    answer: str
    sources: List[Source]
    latency_ms: float
    rewritten_queries: Optional[List[str]] = None


# ========== FastAPI App ==========

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动
    print(f"🚀 Starting {settings.app_name} v{settings.app_version}")
    print(f"📊 Debug mode: {settings.debug}")
    print(f"🔧 Log level: {settings.log_level}")
    
    # 初始化组件
    app.state.circuit_breaker = CircuitBreaker(
        "default",
        CircuitBreakerConfig(
            failure_threshold=settings.circuit_breaker.failure_threshold,
            recovery_timeout=settings.circuit_breaker.recovery_timeout
        )
    )
    app.state.rate_limiter = TokenBucket(
        rate=settings.rate_limit.requests_per_minute / 60,
        capacity=settings.rate_limit.burst_size
    )
    
    yield
    
    # 关闭
    print("👋 Shutting down...")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="企业级RAG系统 - 支持文档接入、智能检索、LLM生成",
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


# ========== 依赖注入 ==========

async def get_circuit_breaker():
    return app.state.circuit_breaker


async def get_rate_limiter():
    return app.state.rate_limiter


# ========== API Endpoints ==========

@app.get("/health", response_model=HealthCheck)
async def health_check():
    """健康检查"""
    return HealthCheck(
        status="healthy",
        version=settings.app_version,
        timestamp=time.time()
    )


@app.get("/ready")
async def readiness_check():
    """就绪检查"""
    return {"status": "ready"}


@app.post("/ingest", response_model=IngestResponse)
async def ingest_document(
    request: IngestRequest,
    circuit_breaker: CircuitBreaker = Depends(get_circuit_breaker)
):
    """
    接入文档
    
    支持多种分块策略，默认使用Parent-Child分块
    """
    try:
        # 使用熔断器保护
        if not await circuit_breaker.can_execute():
            raise HTTPException(status_code=503, detail="Service temporarily unavailable")
        
        # 根据策略选择分块器
        if request.chunking_strategy == "parent_child":
            chunker = ParentChildChunker(
                parent_size=settings.chunking.parent_size,
                child_size=settings.chunking.child_size,
                child_overlap=settings.chunking.overlap
            )
        else:
            chunker = ParentChildChunker()  # 默认
        
        # 分块
        parent_chunks = chunker.chunk(request.content)
        
        # 收集所有子块
        all_chunks = []
        for parent in parent_chunks:
            all_chunks.extend(parent.child_chunks)
        
        # 模拟存储（实际应接入向量数据库）
        chunk_ids = [f"chunk_{i}" for i in range(len(all_chunks))]
        
        return IngestResponse(
            success=True,
            num_chunks=len(all_chunks),
            chunk_ids=chunk_ids,
            message=f"Successfully ingested {len(all_chunks)} chunks"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/query", response_model=QueryResponse)
async def query(
    request: QueryRequest,
    circuit_breaker: CircuitBreaker = Depends(get_circuit_breaker),
    rate_limiter: TokenBucket = Depends(get_rate_limiter)
):
    """
    查询接口
    
    支持查询改写、多路检索、LLM生成
    """
    start_time = time.time()
    
    # 限流检查
    if settings.rate_limit.enabled:
        if not await rate_limiter.acquire():
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
    # 熔断检查
    if settings.circuit_breaker.enabled:
        if not await circuit_breaker.can_execute():
            raise HTTPException(status_code=503, detail="Circuit breaker open")
    
    try:
        # 查询改写
        rewritten_queries = None
        if request.enable_rewrite:
            rewriter = QueryRewriter()
            rewrite_result = rewriter.rewrite(request.query, strategies=['multi_query'])
            rewritten_queries = [r.query for r in rewrite_result]
        
        # 模拟检索（实际应接入向量数据库）
        # 这里返回mock数据
        mock_sources = [
            Source(
                content="这是检索到的相关内容1...",
                score=0.92,
                metadata={"source": "doc1"}
            ),
            Source(
                content="这是检索到的相关内容2...",
                score=0.85,
                metadata={"source": "doc2"}
            )
        ]
        
        # 模拟LLM生成
        mock_answer = f"基于检索结果，{request.query}的答案是..."
        
        latency_ms = (time.time() - start_time) * 1000
        
        return QueryResponse(
            query=request.query,
            answer=mock_answer,
            sources=mock_sources,
            latency_ms=latency_ms,
            rewritten_queries=rewritten_queries
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/metrics")
async def metrics():
    """Prometheus指标接口"""
    if not PROMETHEUS_AVAILABLE:
        return JSONResponse(
            content={"status": "prometheus not installed"},
            status_code=503
        )
    
    from fastapi.responses import Response
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )


@app.get("/config")
async def get_config():
    """获取当前配置（仅展示非敏感信息）"""
    return {
        "app_name": settings.app_name,
        "app_version": settings.app_version,
        "debug": settings.debug,
        "llm_provider": settings.llm.provider,
        "llm_model": settings.llm.model,
        "vector_provider": settings.vector_store.provider,
        "chunking_strategy": settings.chunking.strategy,
        "circuit_breaker_enabled": settings.circuit_breaker.enabled,
        "rate_limit_enabled": settings.rate_limit.enabled,
    }


# ========== 启动入口 ==========

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.api.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        workers=settings.workers
    )
