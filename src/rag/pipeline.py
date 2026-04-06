"""
DefaultRAGPipeline - 开箱即用的RAG流水线

把分散的模块串成端到端流程：
文档解析 → 分块 → 向量化 → 存储 → 查询改写 → 检索 → 生成

定位：轻量级脚手架，默认配置开箱即用，同时保留模块可替换能力
"""
import os
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
from services.embedding_service import EmbeddingService
from services.llm_service import LLMService, QwenLLMService
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
    parent_chunk_size: int = 2000
    
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
    answer: str
    citations: List[Dict[str, Any]] = field(default_factory=list)
    rewritten_queries: List[str] = field(default_factory=list)
    retrieved_docs: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class DefaultRAGPipeline:
    """
    默认RAG流水线
    
    开箱即用，一行代码完成文档入库或问答
    
    示例:
        >>> pipeline = DefaultRAGPipeline()
        >>> pipeline.ingest_documents(["doc.pdf", "report.md"])
        >>> result = pipeline.query("文档的核心观点是什么？")
        >>> print(result.answer)
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
        self._llm: Optional[LLMService] = None
        
        # Memory管理器
        self._memory_manager: Optional[MemoryManager] = None
        
        logger.info("DefaultRAGPipeline 创建完成，等待初始化...")
    
    def _ensure_initialized(self):
        """延迟初始化各模块"""
        if self._initialized:
            return
        
        logger.info("开始初始化RAG流水线...")
        
        # 1. 文档解析器
        self._parser = DocumentParser()
        
        # 2. 分块器（父子分块）
        self._chunker = ParentChildChunker(
            chunk_size=self.config.chunk_size,
            chunk_overlap=self.config.chunk_overlap,
            parent_chunk_size=self.config.parent_chunk_size
        )
        
        # 3. Embedding服务
        self._embedder = EmbeddingService(
            model_name=self.config.embedding_model
        )
        
        # 4. 向量存储（简易版）
        os.makedirs(self.config.vector_store_path, exist_ok=True)
        persist_path = os.path.join(self.config.vector_store_path, "vectors.pkl")
        self._vector_store = SimpleVectorStore(persist_path=persist_path)
        
        # 5. 混合检索器
        self._retriever = HybridRetriever(
            vector_store=self._vector_store,
            top_k=self.config.top_k
        )
        
        # 6. 查询改写器
        if self.config.enable_query_rewrite:
            self._query_rewriter = QueryRewriter(
                strategies=self.config.rewrite_strategies
            )
        
        # 7. LLM服务
        if self.config.use_local_llm:
            self._llm = QwenLLMService(
                model_name=self.config.llm_model
            )
        else:
            self._llm = LLMService(
                api_key=self.config.llm_api_key,
                base_url=self.config.llm_base_url,
                model=self.config.llm_model
            )
        
        # 8. Memory管理器
        self._memory_manager = MemoryManager()
        
        self._initialized = True
        logger.info("RAG流水线初始化完成")
    
    def ingest_document(self, file_path: Union[str, Path]) -> IngestResult:
        """
        单文档入库
        
        流程: 解析 → 分块 → 向量化 → 存储
        
        Args:
            file_path: 文档路径
        
        Returns:
            IngestResult: 入库结果
        """
        self._ensure_initialized()
        file_path = str(file_path)
        
        try:
            logger.info(f"开始处理文档: {file_path}")
            
            # 1. 解析文档
            doc = self._parser.parse(file_path)
            if not doc or not doc.text:
                return IngestResult(
                    success=False,
                    file_path=file_path,
                    error="文档解析失败或内容为空"
                )
            
            # 2. 分块（父子分块）
            chunks = self._chunker.chunk(doc.text)
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
                {
                    "source": file_path,
                    "chunk_index": i,
                    "total_chunks": len(chunks)
                }
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
    
    def ingest_documents(
        self,
        file_paths: List[Union[str, Path]],
        show_progress: bool = True
    ) -> List[IngestResult]:
        """
        批量文档入库
        
        Args:
            file_paths: 文档路径列表
            show_progress: 是否显示进度
        
        Returns:
            List[IngestResult]: 各文档入库结果
        """
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
        
        # 汇总
        success_count = sum(1 for r in results if r.success)
        print(f"\n入库完成: {success_count}/{total} 成功")
        
        return results
    
    def query(
        self,
        query: str,
        use_rewrite: bool = True,
        use_citation: bool = True
    ) -> QueryResult:
        """
        问答查询
        
        流程: 查询改写 → 向量化 → 混合检索 → LLM生成
        
        Args:
            query: 用户问题
            use_rewrite: 是否使用查询改写
            use_citation: 是否生成引用标注
        
        Returns:
            QueryResult: 查询结果（含答案、引用、检索文档）
        """
        self._ensure_initialized()
        
        try:
            logger.info(f"开始查询: {query}")
            
            # 1. 查询改写（可选）
            rewritten_queries = []
            if use_rewrite and self._query_rewriter:
                rewritten_queries = self._query_rewriter.rewrite(query)
                logger.info(f"查询改写: {len(rewritten_queries)}个变体")
            
            # 2. 向量化
            query_embedding = self._embedder.encode([query])[0]
            
            # 3. 向量检索
            search_results = self._vector_store.search(
                query_embedding=query_embedding,
                top_k=self.config.top_k
            )
            
            # 转换为统一格式
            retrieved_docs = [
                {
                    "id": doc.id,
                    "text": doc.text,
                    "metadata": doc.metadata,
                    "score": score
                }
                for doc, score in search_results
            ]
            
            # 4. 精排（取前rerank_top_k个）
            if len(retrieved_docs) > self.config.rerank_top_k:
                retrieved_docs = retrieved_docs[:self.config.rerank_top_k]
            
            # 5. LLM生成答案
            if retrieved_docs:
                # 构建上下文
                context_parts = []
                for i, doc in enumerate(retrieved_docs, 1):
                    context_parts.append(f"[{i}] {doc['text']}")
                context = "\n\n".join(context_parts)
                
                # 构建提示
                prompt = f"""根据以下参考资料回答问题：

参考资料：
{context}

问题：{query}

请基于参考资料回答，并在回答中引用相关片段的编号（如[1]、[2]）。如果参考资料中没有相关信息，请明确说明。"""
                
                # 调用LLM生成（模拟，实际使用时应接入真实LLM）
                try:
                    answer = self._llm.generate(prompt, max_tokens=512)
                except Exception as llm_error:
                    # 如果LLM调用失败，返回基于检索结果的简单答案
                    answer = f"[基于检索结果]\n\n我找到了{len(retrieved_docs)}个相关文档片段。\n\n" + \
                             "\n".join([f"[{i+1}] {doc['text'][:150]}..." for i, doc in enumerate(retrieved_docs[:3])])
            else:
                answer = "未检索到相关文档，无法回答该问题。"
            
            # 6. 生成引用
            citations = []
            if use_citation and retrieved_docs:
                citations = self._extract_citations(retrieved_docs)
            
            logger.info(f"查询完成: {query[:50]}...")
            
            return QueryResult(
                query=query,
                answer=answer,
                citations=citations,
                rewritten_queries=rewritten_queries,
                retrieved_docs=retrieved_docs,
                metadata={
                    "retrieved_count": len(retrieved_docs),
                    "use_rewrite": use_rewrite
                }
            )
            
        except Exception as e:
            logger.error(f"查询失败: {query}, 错误: {str(e)}")
            return QueryResult(
                query=query,
                answer=f"查询出错: {str(e)}",
                error=str(e)
            )
    
    def _extract_citations(
        self,
        retrieved_docs: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """提取引用信息"""
        citations = []
        for idx, doc in enumerate(retrieved_docs, 1):
            citation = {
                "id": idx,
                "source": doc.get("metadata", {}).get("source", "未知"),
                "content": doc.get("text", "")[:200] + "...",
                "score": doc.get("score", 0.0)
            }
            citations.append(citation)
        return citations
    
    def chat(
        self,
        query: str,
        session_id: Optional[str] = None,
        user_id: str = "default_user",
        use_memory: bool = True
    ) -> QueryResult:
        """
        对话式问答（支持多轮上下文）
        
        接入Memory四层架构：
        - 超短期：当前会话上下文
        - 短期：近7天历史对话
        - 长期：用户画像与偏好
        
        Args:
            query: 用户问题
            session_id: 会话ID（用于上下文追踪）
            user_id: 用户ID
            use_memory: 是否使用历史上下文
        
        Returns:
            QueryResult: 查询结果
        """
        self._ensure_initialized()
        
        # 生成会话ID
        if session_id is None:
            import uuid
            session_id = str(uuid.uuid4())[:8]
        
        try:
            # 1. 检索历史上下文（Memory四层）
            history_context = ""
            if use_memory and self._memory_manager:
                # 获取当前会话的超短期记忆
                ultra_short_memories = self._memory_manager.get_memories(
                    user_id=user_id,
                    session_id=session_id,
                    layer=MemoryLayer.ULTRA_SHORT,
                    limit=5
                )
                
                # 获取短期记忆（近7天）
                short_memories = self._memory_manager.get_memories(
                    user_id=user_id,
                    layer=MemoryLayer.SHORT,
                    limit=3
                )
                
                # 构建历史上下文
                history_parts = []
                
                # 添加超短期记忆（当前会话）
                if ultra_short_memories:
                    history_parts.append("当前会话历史：")
                    for mem in reversed(ultra_short_memories):  # 按时间正序
                        history_parts.append(f"用户: {mem.content}")
                
                # 添加短期记忆（近7天）
                if short_memories:
                    history_parts.append("\n近期相关对话：")
                    for mem in short_memories[:2]:  # 只取最相关的2条
                        history_parts.append(f"- {mem.content[:100]}...")
                
                history_context = "\n".join(history_parts)
            
            # 2. 向量检索当前查询
            query_embedding = self._embedder.encode([query])[0]
            search_results = self._vector_store.search(
                query_embedding=query_embedding,
                top_k=self.config.top_k
            )
            
            retrieved_docs = [
                {
                    "id": doc.id,
                    "text": doc.text,
                    "metadata": doc.metadata,
                    "score": score
                }
                for doc, score in search_results
            ]
            
            # 3. 构建带上下文的提示
            context_parts = []
            
            # 添加历史对话
            if history_context:
                context_parts.append(f"【对话上下文】\n{history_context}\n")
            
            # 添加检索到的文档
            if retrieved_docs:
                context_parts.append("【参考资料】")
                for i, doc in enumerate(retrieved_docs, 1):
                    context_parts.append(f"[{i}] {doc['text']}")
            
            context = "\n\n".join(context_parts)
            
            # 4. 生成提示
            prompt = f"""你是一个智能助手，请根据对话上下文和参考资料回答用户问题。

{context}

【用户问题】
{query}

请基于以上信息回答，并注意：
1. 如果有对话上下文，请保持回答的连贯性
2. 引用参考资料时使用[1]、[2]等标注
3. 如果信息不足，请明确说明
"""
            
            # 5. 调用LLM生成
            answer = self._llm.generate(prompt)
            
            # 6. 保存到记忆（超短期）
            if self._memory_manager:
                # 保存用户查询
                self._memory_manager.add_ultra_short_memory(
                    user_id=user_id,
                    session_id=session_id,
                    content=query,
                    metadata={"type": "user_query"}
                )
                # 保存助手回答
                self._memory_manager.add_ultra_short_memory(
                    user_id=user_id,
                    session_id=session_id,
                    content=answer,
                    metadata={"type": "assistant_response"}
                )
            
            # 7. 提取引用
            citations = self._extract_citations(retrieved_docs)
            
            return QueryResult(
                query=query,
                answer=answer,
                citations=citations,
                retrieved_docs=retrieved_docs,
                metadata={
                    "session_id": session_id,
                    "retrieved_count": len(retrieved_docs),
                    "use_memory": use_memory,
                    "has_history": bool(history_context)
                }
            )
            
        except Exception as e:
            logger.error(f"对话查询失败: {query}, 错误: {str(e)}")
            return QueryResult(
                query=query,
                answer=f"对话出错: {str(e)}",
                error=str(e)
            )
    
    def get_stats(self) -> Dict[str, Any]:
        """获取流水线统计信息"""
        return {
            "initialized": self._initialized,
            "config": {
                "chunk_size": self.config.chunk_size,
                "embedding_model": self.config.embedding_model,
                "llm_model": self.config.llm_model,
                "top_k": self.config.top_k
            }
        }
