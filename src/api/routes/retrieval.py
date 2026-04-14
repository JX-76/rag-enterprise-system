"""
Retrieval Routes - 检索路由
"""
import time
from typing import List, Dict, Any, Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from src.core.rag_engine import RAGEngine
from src.core.logging import get_logger
from src.core.retrieval_filters import RetrievalAccessContext

router = APIRouter()
logger = get_logger(__name__)


class RetrieveRequest(BaseModel):
    """检索请求"""
    query: str = Field(..., min_length=1, max_length=1000)
    top_k: int = Field(10, ge=1, le=50)
    rewrite: bool = Field(True)
    rerank: bool = Field(True)
    tenant_id: Optional[str] = Field(None, description="租户ID，用于 access-aware retrieval")
    role: Optional[str] = Field(None, description="角色，用于 metadata / ACL filtering")
    allowed_doc_ids: List[str] = Field(default_factory=list, description="允许访问的文档ID列表")
    metadata_filters: Dict[str, Any] = Field(default_factory=dict, description="额外的 metadata 过滤条件")


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
    access_context: Dict[str, Any]


@router.post("", response_model=RetrieveResponse)
async def retrieve(
    request: Request,
    retrieve_request: RetrieveRequest
):
    """仅检索接口，支持 access-aware filtering。"""
    request_id = getattr(request.state, 'request_id', 'unknown')
    start_time = time.time()
    
    logger.info(f"[{request_id}] Retrieve: {retrieve_request.query}")
    
    try:
        engine = RAGEngine()
        access_context = RetrievalAccessContext(
            tenant_id=retrieve_request.tenant_id,
            role=retrieve_request.role,
            allowed_doc_ids=retrieve_request.allowed_doc_ids,
            metadata_filters=retrieve_request.metadata_filters,
        )
        
        results = await engine.retrieve(
            query=retrieve_request.query,
            top_k=retrieve_request.top_k,
            rewrite=retrieve_request.rewrite,
            rerank=retrieve_request.rerank,
            access_context=access_context,
        )
        
        latency = (time.time() - start_time) * 1000
        
        return RetrieveResponse(
            query=retrieve_request.query,
            results=[RetrieveResult(**r) for r in results],
            request_id=request_id,
            latency_ms=latency,
            access_context=access_context.to_dict(),
        )
        
    except Exception as e:
        logger.error(f"[{request_id}] Retrieve failed: {e}", exc_info=True)
        raise
