"""
配置管理 - 使用Pydantic Settings
支持环境变量、.env文件、默认值
"""
from typing import List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMConfig(BaseSettings):
    """LLM配置"""
    model_config = SettingsConfigDict(env_prefix="LLM_")
    
    provider: str = Field(default="openai", description="LLM提供商: openai, anthropic, local")
    model: str = Field(default="gpt-3.5-turbo", description="模型名称")
    api_key: Optional[str] = Field(default=None, description="API密钥")
    base_url: Optional[str] = Field(default=None, description="自定义API基础URL")
    temperature: float = Field(default=0.7, ge=0, le=2)
    max_tokens: int = Field(default=2000, ge=1)
    timeout: float = Field(default=30.0, ge=1)


class VectorStoreConfig(BaseSettings):
    """向量存储配置"""
    model_config = SettingsConfigDict(env_prefix="VECTOR_")
    
    provider: str = Field(default="chromadb", description="向量数据库: chromadb, milvus, qdrant")
    collection_name: str = Field(default="rag_documents")
    embedding_model: str = Field(default="BAAI/bge-small-zh-v1.5")
    embedding_dim: int = Field(default=512)
    distance_metric: str = Field(default="cosine")
    
    # ChromaDB特定配置
    chroma_persist_dir: str = Field(default="./chroma_db")
    
    # Milvus特定配置
    milvus_host: str = Field(default="localhost")
    milvus_port: int = Field(default=19530)


class RetrievalConfig(BaseSettings):
    """检索配置"""
    model_config = SettingsConfigDict(env_prefix="RETRIEVAL_")
    
    top_k: int = Field(default=5, ge=1, le=100)
    enable_hybrid: bool = Field(default=True)
    dense_weight: float = Field(default=0.5, ge=0, le=1)
    bm25_weight: float = Field(default=0.5, ge=0, le=1)
    rrf_k: int = Field(default=60)
    enable_rerank: bool = Field(default=False)


class ChunkingConfig(BaseSettings):
    """分块配置"""
    model_config = SettingsConfigDict(env_prefix="CHUNKING_")
    
    strategy: str = Field(default="parent_child", description="分块策略: parent_child, recursive")
    parent_size: int = Field(default=1000)
    child_size: int = Field(default=200)
    overlap: int = Field(default=40)
    respect_semantic_boundaries: bool = Field(default=True)


class CircuitBreakerConfig(BaseSettings):
    """熔断器配置"""
    model_config = SettingsConfigDict(env_prefix="CIRCUIT_")
    
    enabled: bool = Field(default=True)
    failure_threshold: int = Field(default=5)
    recovery_timeout: float = Field(default=30.0)
    half_open_max_calls: int = Field(default=3)
    success_threshold: int = Field(default=2)


class RateLimitConfig(BaseSettings):
    """限流配置"""
    model_config = SettingsConfigDict(env_prefix="RATE_LIMIT_")
    
    enabled: bool = Field(default=True)
    requests_per_minute: int = Field(default=60)
    burst_size: int = Field(default=10)


class AppConfig(BaseSettings):
    """应用主配置"""
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    # 应用基础配置
    app_name: str = Field(default="RAG Enterprise System")
    app_version: str = Field(default="1.0.0")
    debug: bool = Field(default=False)
    log_level: str = Field(default="INFO")
    
    # 服务器配置
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)
    workers: int = Field(default=1)
    
    # 子配置
    llm: LLMConfig = Field(default_factory=LLMConfig)
    vector_store: VectorStoreConfig = Field(default_factory=VectorStoreConfig)
    retrieval: RetrievalConfig = Field(default_factory=RetrievalConfig)
    chunking: ChunkingConfig = Field(default_factory=ChunkingConfig)
    circuit_breaker: CircuitBreakerConfig = Field(default_factory=CircuitBreakerConfig)
    rate_limit: RateLimitConfig = Field(default_factory=RateLimitConfig)
    
    # 监控配置
    enable_metrics: bool = Field(default=True)
    metrics_port: int = Field(default=9090)


# 全局配置实例
settings = AppConfig()
