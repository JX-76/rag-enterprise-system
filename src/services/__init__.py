"""
Services package - 外部服务封装
"""
from .embedding_service import EmbeddingService, get_embedding_service
from .llm_service import BaseLLM, LocalLLM, APILLM, LLMResponse

__all__ = [
    "EmbeddingService",
    "get_embedding_service",
    "LLMService",
    "get_llm_service",
    "LLMResponse",
]
