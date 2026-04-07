"""
DefaultRAGPipeline - 开箱即用的RAG流水线

把分散的模块串成端到端流程：
文档解析 → 分块 → 向量化 → 存储 → 查询改写 → 检索 → 生成

定位：轻量级脚手架，默认配置开箱即用，同时保留模块可替换能力
"""
import os
import uuid
from datetime import datetime
from typing import List, Dict, Optional, Union, Any
from dataclasses import dataclass, field
from pathlib import Path
import logging

# 导入已实现的模块 (使用绝对导入避免路径问题)
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from ingestion.document_parser import DocumentParser
from ingestion.parent_child_chunker import ParentChildChunker
from services.embedding_service import EmbeddingService, EmbeddingConfig
from services.llm_service import BaseLLM, LocalLLM, APILLM
from retrieval.hybrid_search import HybridRetriever
from retrieval.simple_vector_store import SimpleVectorStore
from rag.query_rewriter import QueryRewriter

# Memory四层架构
from memory import MemoryManager, MemoryLayer
from memory.memory_types import UltraShortTermMemory


logger = logging.getLogger(__name__)


@dataclass
class RAGConfig:
    """RAG流水线配置"""
    # 文档处理
    chunk_size: int = 500
    chunk_overlap: int = 50
    
    # 向量配置
    embedding_model: str = "BAAI/bge-small-zh-v1.5"
    vector_store_path: str = "./data/vector_db"
    
    # 检索配置
    top_k: int = 10
    use_hybrid: bool = True
    rerank_top_k: int = 5
    
    # LLM配置
    llm_model: str = "qwen2.5-7b-instruct"
    llm_api_key: Optional[str] = None
    llm_base_url: Optional[str] = None
    use_local_llm: bool = True
    
    # 查询改写
    enable_query_rewrite: bool = True
    rewrite_strategies: List[str] = field(default_factory=lambda: ["multi_query"])


@dataclass
class IngestResult:
    """文档入库结果"""
    success: bool
    file_path: str
    chunks_count: int = 0
    error: Optional[str] = None


@dataclass
class QueryResult:
    """查询结果"""
    query: str
    answer: str = ""
    citations: List[Dict[str, Any]] = field(default_factory=list)
    rewritten_queries: List[str] = field(default_factory=list)
    retrieved_docs: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class DefaultRAGPipeline:
    """
    默认RAG流水线
    
    开箱即用，一行代码完成文档入库或问答
    """
    
    def __init__(self, config: Optional[RAGConfig] = None):
        self.config = config or RAGConfig()
        self._initialized = False
        
        # 各模块实例（延迟初始化）
        self._parser: Optional[DocumentParser] = None
        self._chunker: Optional[ParentChildChunker] = None
        self._embedder: Optional[EmbeddingService] = None
        self._vector_store: Optional[SimpleVectorStore] = None
        self._retriever: Optional[HybridRetriever] = None
        self._query_rewriter: Optional[QueryRewriter] = None
        self._llm: Optional[BaseLLM] = None
        self._memory_manager: Optional[MemoryManager] = None
        
        logger.info("DefaultRAGPipeline 创建完成")
    
    def _ensure_initialized(self):
        """延迟初始化各模块"""
        if self._initialized:
            return
        
        logger.info("开始初始化RAG流水线...")
        
        # 1. 文档解析器
        self._parser = DocumentParser()
        
        # 2. 分块器
        self._chunker = ParentChildChunker(
            parent_size=self.config.chunk_size * 2,  # 父块大一些
            child_size=self.config.chunk_size,
            child_overlap=self.config.chunk_overlap
        )
        
        # 3. Embedding服务
        embed_config = EmbeddingConfig(
            model_name=self.config.embedding_model
        )
        self._embedder = EmbeddingService(config=embed_config)
        
        # 4. 向量存储
        os.makedirs(self.config.vector_store_path, exist_ok=True)
        persist_path = os.path.join(self.config.vector_store_path, "vectors.pkl")
        self._vector_store = SimpleVectorStore(persist_path=persist_path)
        
        # 5. 混合检索器（暂不使用，query方法直接操作vector_store）
        # self._retriever = HybridRetriever(
        #     dense_retriever=None,
        #     bm25_retriever=None
        # )
        self._retriever = None
        
        # 6. 查询改写器
        if self.config.enable_query_rewrite:
            self._query_rewriter = QueryRewriter(
                llm_client=None  # 暂不使用LLM，使用简单改写策略
            )
        
        # 7. Memory管理器
        self._memory_manager = MemoryManager()
        
        self._initialized = True
        logger.info("RAG流水线初始化完成")
    
    def ingest_document(self, file_path: Union[str, Path]) -> IngestResult:
        """单文档入库"""
        self._ensure_initialized()
        file_path = str(file_path)
        
        try:
            logger.info(f"开始处理文档: {file_path}")
            
            # 1. 解析文档
            doc = self._parser.parse(file_path)
            if not doc or not doc.chunks:
                return IngestResult(
                    success=False,
                    file_path=file_path,
                    error="文档解析失败或内容为空"
                )
            
            # 2. 合并所有chunks的文本
            full_text = "\n".join([chunk.text for chunk in doc.chunks])
            chunks = self._chunker.chunk(full_text)
            if not chunks:
                return IngestResult(
                    success=False,
                    file_path=file_path,
                    error="文档分块失败"
                )
            
            # 3. 向量化
            chunk_texts = [chunk.text for chunk in chunks]
            embeddings = self._embedder.encode(chunk_texts)
            
            # 4. 存入向量库
            metadatas = [
                {"source": file_path, "chunk_index": i}
                for i in range(len(chunks))
            ]
            self._vector_store.add_documents(chunk_texts, embeddings, metadatas)
            
            logger.info(f"文档处理完成: {file_path}, 共{len(chunks)}个分块")
            
            return IngestResult(
                success=True,
                file_path=file_path,
                chunks_count=len(chunks)
            )
            
        except Exception as e:
            logger.error(f"文档入库失败: {file_path}, 错误: {str(e)}")
            return IngestResult(
                success=False,
                file_path=file_path,
                error=str(e)
            )
    
    def ingest_documents(self, file_paths: List[Union[str, Path]], show_progress: bool = True) -> List[IngestResult]:
        """批量文档入库"""
        results = []
        total = len(file_paths)
        
        for idx, file_path in enumerate(file_paths, 1):
            if show_progress:
                print(f"[{idx}/{total}] 处理: {file_path}")
            
            result = self.ingest_document(file_path)
            results.append(result)
            
            if result.success:
                print(f"  ✓ 成功: {result.chunks_count}个分块")
            else:
                print(f"  ✗ 失败: {result.error}")
        
        success_count = sum(1 for r in results if r.success)
        print(f"\n入库完成: {success_count}/{total} 成功")
        
        return results
    
    def query(self, query: str, use_rewrite: bool = True) -> QueryResult:
        """问答查询"""
        self._ensure_initialized()
        
        try:
            logger.info(f"开始查询: {query}")
            
            # 1. 查询改写
            rewritten_queries = []
            if use_rewrite and self._query_rewriter:
                rewritten_queries = self._query_rewriter.rewrite(query)
            
            # 2. 向量化
            query_embedding = self._embedder.encode([query])[0]
            
            # 3. 向量检索
            search_results = self._vector_store.search(
                query_embedding=query_embedding,
                top_k=self.config.top_k
            )
            
            retrieved_docs = [
                {"id": doc.id, "text": doc.text, "metadata": doc.metadata, "score": score}
                for doc, score in search_results
            ]
            
            # 4. 生成答案
            answer = self._generate_answer(query, retrieved_docs)
            
            # 5. 提取引用
            citations = self._extract_citations(retrieved_docs)
            
            logger.info(f"查询完成: {query[:50]}...")
            
            return QueryResult(
                query=query,
                answer=answer,
                citations=citations,
                rewritten_queries=rewritten_queries,
                retrieved_docs=retrieved_docs,
                metadata={"retrieved_count": len(retrieved_docs)}
            )
            
        except Exception as e:
            logger.error(f"查询失败: {query}, 错误: {str(e)}")
            return QueryResult(
                query=query,
                answer=f"查询出错: {str(e)}",
                metadata={"error": str(e)}
            )
    
    def _generate_answer(self, query: str, retrieved_docs: List[Dict]) -> str:
        """生成答案（简化版）"""
        if not retrieved_docs:
            return "未检索到相关文档。"
        
        # 简单的摘要式回答
        context = "\n\n".join([f"[{i+1}] {doc['text'][:200]}..." 
                              for i, doc in enumerate(retrieved_docs[:3])])
        
        return f"基于检索结果，找到{len(retrieved_docs)}个相关片段：\n\n{context}"
    
    def _extract_citations(self, retrieved_docs: List[Dict]) -> List[Dict]:
        """提取引用信息"""
        return [
            {
                "id": idx,
                "source": doc.get("metadata", {}).get("source", "未知"),
                "content": doc.get("text", "")[:200] + "...",
                "score": doc.get("score", 0.0)
            }
            for idx, doc in enumerate(retrieved_docs, 1)
        ]
    
    def chat(
        self,
        query: str,
        session_id: Optional[str] = None,
        user_id: str = "default_user",
        use_memory: bool = True,
        max_history_turns: int = 5
    ) -> QueryResult:
        """
        对话式问答 - 接入Memory四层架构

        记忆层级：
        - 超短期：当前会话上下文（自动管理）
        - 短期：近7天对话历史（Redis）
        - 长期：用户画像与偏好（PostgreSQL）

        Args:
            query: 用户问题
            session_id: 会话ID（用于上下文追踪）
            user_id: 用户ID
            use_memory: 是否使用记忆
            max_history_turns: 最大历史轮数
        """
        self._ensure_initialized()

        # 生成session_id
        if session_id is None:
            session_id = str(uuid.uuid4())[:8]

        logger.info(f"对话查询 [session={session_id}]: {query}")

        # 1. 检索历史对话上下文
        history_context = ""
        if use_memory and self._memory_manager:
            try:
                # 获取当前会话上下文（超短期记忆）
                session_context = self._memory_manager.get_session_context(user_id, session_id)

                if session_context:
                    history_context = f"当前会话历史：\n{session_context}"
                    logger.info(f"检索到会话上下文 [session={session_id}]")

            except Exception as e:
                logger.warning(f"记忆检索失败: {e}")
                history_context = ""

        # 2. 文档检索（使用query方法）
        result = self.query(query, use_rewrite=True)

        # 3. 如果有历史上下文，增强回答
        if history_context and result.answer:
            enhanced_answer = f"""{result.answer}

---
[基于上下文理解]
{history_context}"""
            result.answer = enhanced_answer

        # 4. 保存当前对话到记忆
        if use_memory and self._memory_manager:
            try:
                # 使用 add_to_session_context 方法保存对话
                self._memory_manager.add_to_session_context(
                    user_id=user_id,
                    session_id=session_id,
                    role="user",
                    content=query,
                    metadata={"type": "user_query", "timestamp": datetime.now().isoformat()}
                )

                self._memory_manager.add_to_session_context(
                    user_id=user_id,
                    session_id=session_id,
                    role="assistant",
                    content=result.answer[:500],  # 限制长度
                    metadata={"type": "assistant_response", "timestamp": datetime.now().isoformat()}
                )

                logger.info(f"对话已保存到记忆 [session={session_id}]")

            except Exception as e:
                logger.warning(f"记忆保存失败: {e}")

        # 5. 在metadata中添加会话信息
        result.metadata["session_id"] = session_id
        result.metadata["user_id"] = user_id
        result.metadata["history_used"] = bool(history_context)

        return result
    
    def clear_session_memory(self, session_id: str) -> bool:
        """清理指定会话的记忆"""
        if self._memory_manager:
            try:
                self._memory_manager.clear_session(session_id)
                logger.info(f"会话记忆已清理 [session={session_id}]")
                return True
            except Exception as e:
                logger.warning(f"清理会话记忆失败: {e}")
        return False

    def get_memory_stats(self, user_id: str = "default_user") -> Dict[str, Any]:
        """获取记忆统计信息"""
        if not self._memory_manager:
            return {"error": "MemoryManager未初始化"}

        try:
            # 获取各层记忆数量
            ultra_count = len(self._memory_manager._ultra_short_store.get(user_id, []))
            short_count = len(self._memory_manager._short_store.get(user_id, []))

            return {
                "ultra_short_memory_count": ultra_count,
                "short_term_memory_count": short_count,
                "memory_layers": ["ultra_short", "short_term"],
                "status": "active"
            }
        except Exception as e:
            return {"error": str(e)}

    def get_stats(self) -> Dict[str, Any]:
        """获取流水线统计信息"""
        return {
            "initialized": self._initialized,
            "config": {
                "chunk_size": self.config.chunk_size,
                "embedding_model": self.config.embedding_model,
                "top_k": self.config.top_k
            },
            "vector_store": self._vector_store.get_stats() if self._vector_store else {},
            "memory": self.get_memory_stats()
        }
