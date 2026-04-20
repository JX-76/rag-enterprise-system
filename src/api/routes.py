"""
Legacy demo routes kept for reference.

This module is **not** the canonical public API path.
Current maintained entrypoint is `src.main:app` with route modules under `src/api/routes/`.

Why this file still exists:
1. preserve an earlier single-file demo implementation for comparison
2. provide a lightweight reference for upload/list/delete flow ideas
3. avoid presenting these handlers as the production-ready RAG main path
"""
from typing import List, Optional
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
import logging
import uuid
from datetime import datetime

from ..document.parser import DocumentParser, ParseError
from ..document.chunker import SemanticChunker
from ..vector.milvus_store import MilvusStore
from ..llm.base import LLMBase
from ..llm.local_model import LocalLLM
from ..llm.api_model import DashScopeLLM
from ..rag.retriever import HybridRetriever
from ..rag.generator import RAGGenerator
from ...config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1")

# 全局组件（简化版，实际应用应使用依赖注入）
parser = DocumentParser()
chunker = SemanticChunker(chunk_size=settings.CHUNK_SIZE, chunk_overlap=settings.CHUNK_OVERLAP)
vector_store = None
llm = None
retriever = None
generator = None

# SQLite存储（简化）
documents_db = {}  # doc_id -> metadata

def init_components():
    """初始化组件"""
    global vector_store, llm, retriever, generator
    
    # 向量库
    vector_store = MilvusStore(
        collection_name=settings.MILVUS_COLLECTION,
        dimension=settings.VECTOR_DIM,
        host=settings.MILVUS_HOST,
        port=settings.MILVUS_PORT
    )
    vector_store.connect()
    
    # 大模型
    if settings.LLM_MODE == "local":
        llm = LocalLLM(base_url=settings.LOCAL_LLM_URL)
    else:
        llm = DashScopeLLM(api_key=settings.DASHSCOPE_API_KEY)
    
    # 检索器
    retriever = HybridRetriever(
        vector_store=vector_store,
        dense_weight=settings.DENSE_WEIGHT,
        bm25_weight=settings.BM25_WEIGHT,
        rrf_k=settings.RRF_K
    )
    
    # 生成器
    generator = RAGGenerator(llm=llm)
    
    logger.info("组件初始化完成")


# ============ 数据模型 ============

class DocumentInfo(BaseModel):
    """文档信息"""
    id: str
    filename: str
    file_type: str
    status: str
    created_at: str
    chunk_count: int = 0

class DocumentListResponse(BaseModel):
    """文档列表响应"""
    documents: List[DocumentInfo]
    total: int

class QuestionRequest(BaseModel):
    """问答请求"""
    question: str = Field(..., min_length=1, max_length=1000)
    session_id: str = Field(default="default")
    temperature: float = Field(default=0.3, ge=0, le=1)

class SourceInfo(BaseModel):
    """来源信息"""
    id: str
    text: str
    score: float

class HallucinationCheck(BaseModel):
    """幻觉检测结果"""
    is_hallucination: bool
    confidence: float
    reason: str

class QuestionResponse(BaseModel):
    """问答响应"""
    answer: str
    sources: List[SourceInfo]
    hallucination_check: HallucinationCheck
    retrieval_quality: str


# ============ 接口 ============

@router.post("/documents/upload", response_model=DocumentInfo)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...)
):
    """
    上传文档
    
    支持PDF、DOCX、TXT格式，自动解析、分块、向量化
    """
    doc_id = str(uuid.uuid4())
    
    try:
        # 校验文件
        content_type = file.content_type or "application/octet-stream"
        file_type = parser.validate_file(await file.read(), content_type, file.filename)
        
        # 重新读取（validate消耗了stream）
        await file.seek(0)
        content = await file.read()
        
        # 解析文档
        parsed = parser.parse(content, content_type, file.filename)
        
        # 分块
        chunks = chunker.chunk(parsed.text, doc_id)
        
        # TODO: 向量化并入库（需要embedding服务）
        # 简化版：仅记录元数据
        
        # 存储元数据
        documents_db[doc_id] = {
            "id": doc_id,
            "filename": file.filename,
            "file_type": file_type,
            "status": "processing",
            "created_at": datetime.now().isoformat(),
            "chunk_count": len(chunks),
            "text": parsed.text[:1000]  # 简化存储
        }
        
        logger.info(f"文档上传成功: {file.filename}, {len(chunks)} 块")
        
        return DocumentInfo(
            id=doc_id,
            filename=file.filename,
            file_type=file_type,
            status="processing",
            created_at=documents_db[doc_id]["created_at"],
            chunk_count=len(chunks)
        )
        
    except ParseError as e:
        logger.error(f"文档解析失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"上传失败: {e}")
        raise HTTPException(status_code=500, detail=f"上传失败: {str(e)}")


@router.get("/documents", response_model=DocumentListResponse)
async def list_documents():
    """获取文档列表"""
    docs = [
        DocumentInfo(
            id=d["id"],
            filename=d["filename"],
            file_type=d["file_type"],
            status=d["status"],
            created_at=d["created_at"],
            chunk_count=d.get("chunk_count", 0)
        )
        for d in documents_db.values()
    ]
    
    return DocumentListResponse(documents=docs, total=len(docs))


@router.get("/documents/{doc_id}", response_model=DocumentInfo)
async def get_document(doc_id: str):
    """获取文档详情"""
    if doc_id not in documents_db:
        raise HTTPException(status_code=404, detail="文档不存在")
    
    d = documents_db[doc_id]
    return DocumentInfo(
        id=d["id"],
        filename=d["filename"],
        file_type=d["file_type"],
        status=d["status"],
        created_at=d["created_at"],
        chunk_count=d.get("chunk_count", 0)
    )


@router.delete("/documents/{doc_id}")
async def delete_document(doc_id: str):
    """删除文档"""
    if doc_id not in documents_db:
        raise HTTPException(status_code=404, detail="文档不存在")
    
    # TODO: 删除向量库中的数据
    if vector_store:
        try:
            vector_store.delete_by_doc_id(doc_id)
        except Exception as e:
            logger.error(f"删除向量失败: {e}")
    
    del documents_db[doc_id]
    
    return {"message": "删除成功", "doc_id": doc_id}


@router.post("/chat/ask", response_model=QuestionResponse)
async def ask_question(request: QuestionRequest):
    """
    问答接口
    
    执行RAG流程：检索 -> 生成回答
    """
    try:
        # 检查是否有文档
        if not documents_db:
            return QuestionResponse(
                answer="暂无文档，请先上传文档",
                sources=[],
                hallucination_check=HallucinationCheck(
                    is_hallucination=False,
                    confidence=0.0,
                    reason="无文档"
                ),
                retrieval_quality="no_docs"
            )
        
        # TODO: 实际实现需要：
        # 1. 向量化查询
        # 2. 检索相关文档
        # 3. 生成回答
        
        # 简化版：返回模拟结果
        return QuestionResponse(
            answer=f"这是关于\"{request.question}\"的回答（演示模式，实际需接入完整RAG流程）",
            sources=[
                SourceInfo(
                    id="doc_001",
                    text="示例文档片段...",
                    score=0.95
                )
            ],
            hallucination_check=HallucinationCheck(
                is_hallucination=False,
                confidence=0.8,
                reason="演示模式"
            ),
            retrieval_quality="demo"
        )
        
    except Exception as e:
        logger.error(f"问答失败: {e}")
        raise HTTPException(status_code=500, detail=f"问答失败: {str(e)}")


@router.get("/health")
async def health_check():
    """健康检查"""
    status = {
        "status": "ok",
        "documents_count": len(documents_db),
        "vector_store_connected": vector_store.health_check() if vector_store else False,
        "llm_healthy": llm.health_check() if llm else False
    }
    return status
