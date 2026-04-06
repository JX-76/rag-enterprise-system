"""
LangChain集成示例
展示如何将本项目与LangChain框架结合使用
"""
import os
from typing import List

# LangChain导入
from langchain import OpenAI, LLMChain, PromptTemplate
from langchain.schema import Document as LCDocument
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.vectorstores import Chroma
from langchain.embeddings import HuggingFaceEmbeddings
from langchain.chains import RetrievalQA
from langchain.callbacks import get_openai_callback

# 本项目自定义模块
from src.ingestion.parent_child_chunker import ParentChildChunker
from src.ingestion.document_parser import DocumentParser
from src.api.middleware.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
from src.rag.query_rewriter import QueryRewriter


class CustomRAGPipeline:
    """
    自定义RAG Pipeline
    
    结合LangChain的生态 + 本项目的定制模块
    """
    
    def __init__(
        self,
        embedding_model: str = "BAAI/bge-small-zh-v1.5",
        llm_model: str = "gpt-3.5-turbo",
        use_custom_chunker: bool = True
    ):
        self.use_custom_chunker = use_custom_chunker
        
        # 初始化Embedding模型
        self.embeddings = HuggingFaceEmbeddings(
            model_name=embedding_model,
            model_kwargs={'device': 'cpu'},
            encode_kwargs={'normalize_embeddings': True}
        )
        
        # 初始化LLM
        self.llm = OpenAI(
            model_name=llm_model,
            temperature=0.7,
            max_tokens=2000
        )
        
        # 初始化熔断器（本项目的模块）
        self.circuit_breaker = CircuitBreaker(
            "openai",
            CircuitBreakerConfig(
                failure_threshold=3,
                recovery_timeout=30.0
            )
        )
        
        # 向量存储
        self.vectorstore = None
        self.qa_chain = None
    
    def ingest_documents(
        self,
        documents: List[str],
        collection_name: str = "default"
    ) -> int:
        """
        接入文档
        
        使用本项目的ParentChildChunker替代LangChain默认分块
        """
        all_chunks = []
        
        for doc_content in documents:
            if self.use_custom_chunker:
                # 使用本项目的父子分块
                chunker = ParentChildChunker(
                    parent_size=1000,
                    child_size=200,
                    child_overlap=40
                )
                parent_chunks = chunker.chunk(doc_content)
                
                # 转换为子块用于检索
                for parent in parent_chunks:
                    for child in parent.child_chunks:
                        # 创建LangChain Document
                        lc_doc = LCDocument(
                            page_content=child.content,
                            metadata={
                                **child.metadata,
                                "parent_id": parent.id,
                                "parent_content": parent.content[:500]  # 父块摘要
                            }
                        )
                        all_chunks.append(lc_doc)
            else:
                # 使用LangChain默认分块（对比用）
                splitter = RecursiveCharacterTextSplitter(
                    chunk_size=200,
                    chunk_overlap=40
                )
                chunks = splitter.split_text(doc_content)
                for chunk in chunks:
                    all_chunks.append(LCDocument(page_content=chunk))
        
        # 存入ChromaDB
        self.vectorstore = Chroma.from_documents(
            documents=all_chunks,
            embedding=self.embeddings,
            collection_name=collection_name
        )
        
        # 创建检索链
        self.qa_chain = RetrievalQA.from_chain_type(
            llm=self.llm,
            chain_type="stuff",
            retriever=self.vectorstore.as_retriever(search_kwargs={"k": 5}),
            return_source_documents=True
        )
        
        return len(all_chunks)
    
    @CircuitBreaker("openai")  # 使用熔断器装饰器
    def query(self, question: str) -> dict:
        """
        查询
        
        使用LangChain的RetrievalQA + 本项目的熔断器保护
        """
        if not self.qa_chain:
            raise ValueError("Please ingest documents first")
        
        # 使用callback追踪token消耗
        with get_openai_callback() as cb:
            result = self.qa_chain.invoke({"query": question})
            
            return {
                "answer": result["result"],
                "sources": [
                    {
                        "content": doc.page_content[:200],
                        "metadata": doc.metadata
                    }
                    for doc in result.get("source_documents", [])
                ],
                "token_usage": {
                    "prompt_tokens": cb.prompt_tokens,
                    "completion_tokens": cb.completion_tokens,
                    "total_cost": cb.total_cost
                }
            }
    
    def query_with_rewrite(self, question: str) -> dict:
        """
        查询 + 查询改写
        
        结合本项目的QueryRewriter
        """
        # 改写查询
        rewriter = QueryRewriter()
        rewritten = rewriter.rewrite(question, strategies=['multi_query'])
        
        # 收集所有改写查询的结果
        all_results = []
        for query_variant in rewritten:
            try:
                result = self.query(query_variant.query)
                all_results.append(result)
            except Exception as e:
                print(f"Query failed for '{query_variant.query}': {e}")
        
        # 合并结果（简单实现：取第一个成功的）
        if all_results:
            return {
                "answer": all_results[0]["answer"],
                "sources": all_results[0]["sources"],
                "rewritten_queries": [r.query for r in rewritten],
                "num_attempts": len(all_results)
            }
        else:
            return {"error": "All query attempts failed"}


def demo():
    """
    演示用法
    """
    # 示例文档
    sample_docs = [
        """
        # 人工智能简介
        
        人工智能（AI）是计算机科学的一个分支，致力于创建能够执行通常需要人类智能的任务的系统。
        
        ## 机器学习
        
        机器学习是AI的核心技术。它使计算机能够从数据中学习，而无需明确编程。
        
        主要类型包括：
        - 监督学习：使用标记数据
        - 无监督学习：从未标记数据中发现模式
        - 强化学习：通过与环境交互学习
        """,
        """
        ## 深度学习
        
        深度学习使用多层神经网络，在图像识别、自然语言处理等领域取得了突破性进展。
        
        Transformer架构是当前最流行的大语言模型基础架构。
        """
    ]
    
    # 创建Pipeline
    print("🚀 初始化RAG Pipeline...")
    pipeline = CustomRAGPipeline(use_custom_chunker=True)
    
    # 接入文档
    print("📄 接入文档...")
    num_chunks = pipeline.ingest_documents(sample_docs)
    print(f"✅ 创建了 {num_chunks} 个分块")
    
    # 查询
    print("\n🔍 查询测试...")
    question = "什么是机器学习？"
    
    try:
        result = pipeline.query(question)
        print(f"\n问题: {question}")
        print(f"回答: {result['answer']}")
        print(f"Token消耗: {result['token_usage']}")
    except Exception as e:
        print(f"❌ 查询失败: {e}")
    
    # 查询+改写
    print("\n🔄 查询+改写测试...")
    try:
        result = pipeline.query_with_rewrite("机器学习是什么？")
        print(f"改写查询: {result.get('rewritten_queries', [])}")
        print(f"回答: {result['answer'][:200]}...")
    except Exception as e:
        print(f"❌ 查询失败: {e}")


if __name__ == "__main__":
    # 检查环境变量
    if not os.getenv("OPENAI_API_KEY"):
        print("⚠️  请设置 OPENAI_API_KEY 环境变量")
        print("示例: export OPENAI_API_KEY='your-key'")
    else:
        demo()
