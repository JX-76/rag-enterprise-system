"""
Retrieval Routes - 检索路由
"""
from fastapi import APIRouter, Request
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import time

from src.core.rag_engine import RAGEngine
from src.core.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


class RetrieveRequest(BaseModel):
    """检索请求"""
    query: str = Field(..., min_length=1, max_length=1000)
    top_k: int = Field(10, ge=1, le=50)
    rewrite: bool = Field(True)
    rerank: bool = Field(True)


class RetrieveResult(BaseModel):
    """检索结果"""
    id: str
    content: str
    score: float
    metadata: Dict[str, Any]


class RetrieveResponse(BaseModel):
    """检索响应"""
    query: str
    results: List[RetrieveResult]
    request_id: str
    latency_ms: float


@router.post("", response_model=RetrieveResponse)
async def retrieve(
    request: Request,
    retrieve_request: RetrieveRequest
):
    """仅检索接口"""
    request_id = getattr(request.state, 'request_id', 'unknown')
    start_time = time.time()
    
    logger.info(f"[{request_id}] Retrieve: {retrieve_request.query}")
    
    try:
        engine = RAGEngine()
        
        results = await engine.retrieve(
            query=retrieve_request.query,
            top_k=retrieve_request.top_k,
            rewrite=retrieve_request.rewrite,
            rerank=retrieve_request.rerank
        )
        
        latency = (time.time() - start_time) * 1000
        
        return RetrieveResponse(
            query=retrieve_request.query,
            results=[RetrieveResult(**r) for r in results],
            request_id=request_id,
            latency_ms=latency
        )
        
    except Exception as e:
        logger.error(f"[{request_id}] Retrieve failed: {e}", exc_info=True)
        raise
