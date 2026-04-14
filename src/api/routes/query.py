"""
Query API - 完整RAG问答接口
"""
import json
import time
from typing import List, Optional, Dict, Any, AsyncGenerator

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.core.rag_engine import RAGEngine
from src.core.logging import get_logger
from src.core.monitoring import metrics
from src.core.retrieval_filters import RetrievalAccessContext

router = APIRouter()
logger = get_logger(__name__)


class QueryRequest(BaseModel):
    """查询请求"""
    query: str = Field(..., description="用户问题", min_length=1, max_length=1000)
    conversation_id: Optional[str] = Field(None, description="会话ID，用于多轮对话")
    top_k: int = Field(5, ge=1, le=20, description="返回结果数量")
    rewrite: bool = Field(True, description="是否启用查询改写")
    rerank: bool = Field(True, description="是否启用重排序")
    stream: bool = Field(False, description="是否流式返回")
    tenant_id: Optional[str] = Field(None, description="租户ID，用于 access-aware retrieval")
    role: Optional[str] = Field(None, description="角色，用于 metadata / ACL filtering")
    allowed_doc_ids: List[str] = Field(default_factory=list, description="允许访问的文档ID列表")
    metadata_filters: Dict[str, Any] = Field(default_factory=dict, description="额外的 metadata 过滤条件")


class Source(BaseModel):
    """引用来源"""
    id: str
    content: str
    score: float
    metadata: Dict[str, Any]


class QueryRoute(BaseModel):
    task_type: str
    route: str
    confidence: float
    reasons: List[str]
    rewrite_enabled: bool
    rerank_enabled: bool
    recommended_top_k: int
    tool_candidate: bool


class SupportInfo(BaseModel):
    has_support: bool
    confidence: float
    reason: str
    citations_count: int = 0


class ExecutionTracePayload(BaseModel):
    trace_id: str
    route: Dict[str, Any]
    fallback_triggered: bool
    notes: List[str]
    stages: List[Dict[str, Any]]


class QueryResponse(BaseModel):
    """查询响应"""
    query: str
    answer: str
    sources: List[Source]
    rewritten_queries: List[str]
    latency_ms: float
    request_id: str
    route: QueryRoute
    support: SupportInfo
    trace: ExecutionTracePayload


class RAGService:
    """RAG服务单例"""
    _instance = None
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = RAGEngine()
        return cls._instance


def _build_access_context(query_request: QueryRequest) -> RetrievalAccessContext:
    return RetrievalAccessContext(
        tenant_id=query_request.tenant_id,
        role=query_request.role,
        allowed_doc_ids=query_request.allowed_doc_ids,
        metadata_filters=query_request.metadata_filters,
    )


async def _stream_query_response(request_id: str, query_request: QueryRequest) -> AsyncGenerator[str, None]:
    start_time = time.time()
    engine = RAGService.get_instance()
    access_context = _build_access_context(query_request)

    yield f"data: {json.dumps({'event': 'start', 'request_id': request_id}, ensure_ascii=False)}\n\n"
    yield f"data: {json.dumps({'event': 'route_pending'}, ensure_ascii=False)}\n\n"

    result = await engine.query(
        query=query_request.query,
        conversation_id=query_request.conversation_id,
        top_k=query_request.top_k,
        rewrite=query_request.rewrite,
        rerank=query_request.rerank,
        trace_id=request_id,
        access_context=access_context,
    )

    answer = result["answer"]
    chunk_size = 80
    for i in range(0, len(answer), chunk_size):
        chunk = answer[i:i + chunk_size]
        yield f"data: {json.dumps({'event': 'chunk', 'delta': chunk}, ensure_ascii=False)}\n\n"

    latency = (time.time() - start_time) * 1000
    payload = {
        "event": "done",
        "request_id": request_id,
        "query": query_request.query,
        "sources": result["sources"],
        "rewritten_queries": result.get("rewritten_queries", []),
        "latency_ms": latency,
        "route": result["route"],
        "support": result["support"],
        "trace": result["trace"],
    }
    yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.post("", response_model=QueryResponse)
async def query(
    request: Request,
    query_request: QueryRequest
):
    """
    完整RAG问答接口
    
    流程：
    1. 轻量 Query Routing
    2. 查询改写 (按路由决定是否启用)
    3. 多路检索 (Dense + Sparse + BM25)
    4. 三阶重排序
    5. LLM生成
    6. Support / Trace 输出
    7. 可选 Streaming 输出
    """
    request_id = getattr(request.state, 'request_id', 'unknown')
    start_time = time.time()
    
    logger.info(f"[{request_id}] Query: {query_request.query}")

    if query_request.stream:
        return StreamingResponse(
            _stream_query_response(request_id, query_request),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
        )
    
    try:
        engine = RAGService.get_instance()
        access_context = _build_access_context(query_request)
        
        result = await engine.query(
            query=query_request.query,
            conversation_id=query_request.conversation_id,
            top_k=query_request.top_k,
            rewrite=query_request.rewrite,
            rerank=query_request.rerank,
            trace_id=request_id,
            access_context=access_context,
        )
        
        latency = (time.time() - start_time) * 1000
        metrics.record_request("query", 200, latency)
        
        return QueryResponse(
            query=query_request.query,
            answer=result["answer"],
            sources=[Source(**s) for s in result["sources"]],
            rewritten_queries=result.get("rewritten_queries", []),
            latency_ms=latency,
            request_id=request_id,
            route=QueryRoute(**result["route"]),
            support=SupportInfo(**result["support"]),
            trace=ExecutionTracePayload(**result["trace"]),
        )
        
    except Exception as e:
        logger.error(f"[{request_id}] Query failed: {e}", exc_info=True)
        latency = (time.time() - start_time) * 1000
        metrics.record_request("query", 500, latency)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/retrieve-only")
async def retrieve_only(
    request: Request,
    query_request: QueryRequest
):
    """仅检索，不生成答案"""
    request_id = getattr(request.state, 'request_id', 'unknown')
    
    try:
        engine = RAGService.get_instance()
        access_context = _build_access_context(query_request)
        
        results = await engine.retrieve(
            query=query_request.query,
            top_k=query_request.top_k,
            rewrite=query_request.rewrite,
            rerank=query_request.rerank,
            access_context=access_context,
        )
        
        return {
            "query": query_request.query,
            "results": results,
            "request_id": request_id,
            "access_context": access_context.to_dict(),
        }
        
    except Exception as e:
        logger.error(f"[{request_id}] Retrieve failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
