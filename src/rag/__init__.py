"""Legacy RAG aggregation package retained for compatibility; prefer `src.core` + `src.retrieval` + `src.generation` for the canonical architecture narrative."""
from .retriever import HybridRetriever, create_retriever
from .generator import RAGGenerator

__all__ = ['HybridRetriever', 'create_retriever', 'RAGGenerator']
