"""
Configuration Management
配置管理 - 支持环境变量和YAML配置
"""
import os
from typing import List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用配置"""
    
    # 基础配置
    APP_NAME: str = "Enterprise RAG System"
    DEBUG: bool = Field(default=False, env="DEBUG")
    HOST: str = Field(default="0.0.0.0", env="HOST")
    PORT: int = Field(default=8000, env="PORT")
    WORKERS: int = Field(default=4, env="WORKERS")
    
    # API密钥
    OPENAI_API_KEY: Optional[str] = Field(default=None, env="OPENAI_API_KEY")
    ANTHROPIC_API_KEY: Optional[str] = Field(default=None, env="ANTHROPIC_API_KEY")
    
    # 模型配置
    EMBEDDING_MODEL: str = Field(default="BAAI/bge-large-zh-v1.5", env="EMBEDDING_MODEL")
    RERANKER_MODEL: str = Field(default="BAAI/bge-reranker-large", env="RERANKER_MODEL")
    LLM_MODEL: str = Field(default="gpt-4", env="LLM_MODEL")
    
    # 向量数据库配置
    VECTOR_STORE_TYPE: str = Field(default="faiss", env="VECTOR_STORE_TYPE")  # faiss, milvus, pgvector
    VECTOR_STORE_HOST: str = Field(default="localhost", env="VECTOR_STORE_HOST")
    VECTOR_STORE_PORT: int = Field(default=19530, env="VECTOR_STORE_PORT")
    
    # 缓存配置
    REDIS_URL: Optional[str] = Field(default=None, env="REDIS_URL")
    CACHE_TTL: int = Field(default=3600, env="CACHE_TTL")  # 秒
    
    # 检索配置
    RETRIEVAL_TOP_K: int = Field(default=20, env="RETRIEVAL_TOP_K")
    RERANK_TOP_K: int = Field(default=5, env="RERANK_TOP_K")
    
    # 性能配置
    ENABLE_HYDE: bool = Field(default=True, env="ENABLE_HYDE")
    ENABLE_MULTI_QUERY: bool = Field(default=True, env="ENABLE_MULTI_QUERY")
    MAX_WORKERS: int = Field(default=5, env="MAX_WORKERS")
    REQUEST_TIMEOUT: int = Field(default=30, env="REQUEST_TIMEOUT")
    
    # 监控配置
    ENABLE_METRICS: bool = Field(default=True, env="ENABLE_METRICS")
    METRICS_PORT: int = Field(default=9090, env="METRICS_PORT")
    LOG_LEVEL: str = Field(default="INFO", env="LOG_LEVEL")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# 全局配置实例
settings = Settings()


# 检索配置
RETRIEVAL_CONFIG = {
    "dense": {
        "model": settings.EMBEDDING_MODEL,
        "weight": 0.4,
        "index_type": "HNSW",
        "ef_construction": 200,
        "ef_search": 128
    },
    "sparse": {
        "model": "naver/splade-cocondenser-ensembledistil",
        "weight": 0.3
    },
    "bm25": {
        "weight": 0.3,
        "k1": 1.5,
        "b": 0.75
    }
}

# 重排序配置
RERANK_CONFIG = {
    "stage1": {
        "model": "BAAI/bge-small-zh",
        "top_k": 30
    },
    "stage2": {
        "model": settings.RERANKER_MODEL,
        "top_k": 10
    },
    "stage3": {
        "position_optimize": True,
        "deduplication": True,
        "max_context_length": 4000
    }
}

# 查询改写配置
REWRITE_CONFIG = {
    "hyde": {
        "enabled": settings.ENABLE_HYDE,
        "temperature": 0.7,
        "max_tokens": 512
    },
    "multi_query": {
        "enabled": settings.ENABLE_MULTI_QUERY,
        "num_queries": 5,
        "temperature": 0.7
    }
}
