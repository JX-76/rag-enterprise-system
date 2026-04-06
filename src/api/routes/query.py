"""
Query API - 完整RAG问答接口
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import time

from src.core.rag_engine import RAGEngine
from src.core.logging import get_logger
from src.core.monitoring import metrics

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


class Source(BaseModel):
    """引用来源"""
    id: str
    content: str
    score: float
    metadata: Dict[str, Any]


class QueryResponse(BaseModel):
    """查询响应"""
    query: str
    answer: str
    sources: List[Source]
    rewritten_queries: List[str]
    latency_ms: float
    request_id: str


class RAGService:
    """RAG服务单例"""
    _instance = None
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = RAGEngine()
        return cls._instance


@router.post("", response_model=QueryResponse)
async def query(
    request: Request,
    query_request: QueryRequest
):
    """
    完整RAG问答接口
    
    流程：
    1. 查询改写 (HyDE + Multi-Query)
    2. 多路检索 (Dense + Sparse + BM25)
    3. 三阶重排序
    4. 上下文压缩
    5. LLM生成
    6. 幻觉检测
    """
    request_id = getattr(request.state, 'request_id', 'unknown')
    start_time = time.time()
    
    logger.info(f"[{request_id}] Query: {query_request.query}")
    
    try:
        engine = RAGService.get_instance()
        
        result = await engine.query(
            query=query_request.query,
            conversation_id=query_request.conversation_id,
            top_k=query_request.top_k,
            rewrite=query_request.rewrite,
            rerank=query_request.rerank
        )
        
        latency = (time.time() - start_time) * 1000
        
        # 记录指标
        metrics.record_request("query", 200, latency)
        
        return QueryResponse(
            query=query_request.query,
            answer=result["answer"],
            sources=[Source(**s) for s in result["sources"]],
            rewritten_queries=result.get("rewritten_queries", []),
            latency_ms=latency,
            request_id=request_id
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
        
        results = await engine.retrieve(
            query=query_request.query,
            top_k=query_request.top_k,
            rewrite=query_request.rewrite,
            rerank=query_request.rerank
        )
        
        return {
            "query": query_request.query,
            "results": results,
            "request_id": request_id
        }
        
    except Exception as e:
        logger.error(f"[{request_id}] Retrieve failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
