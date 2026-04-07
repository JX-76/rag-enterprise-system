"""
全局配置文件 - RAG Demo 配置集中管理
支持开发/演示双环境切换
"""

from typing import Optional
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """应用配置"""
    
    # 应用基础配置
    APP_NAME: str = "RAG Demo"
    APP_VERSION: str = "2.0.0"
    DEBUG: bool = False
    
    # FastAPI 配置
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # 数据存储
    SQLITE_DB_PATH: str = "./data/rag_demo.db"
    UPLOAD_DIR: str = "./data/uploads"
    
    # Milvus 配置
    MILVUS_HOST: str = "localhost"
    MILVUS_PORT: int = 19530
    MILVUS_COLLECTION: str = "rag_documents"
    VECTOR_DIM: int = 768  # BGE-small 维度
    
    # Embedding 配置
    EMBEDDING_MODEL: str = "BAAI/bge-small-zh-v1.5"
    EMBEDDING_DEVICE: str = "cpu"  # cpu/cuda
    
    # 文档分块配置
    CHUNK_SIZE: int = 512
    CHUNK_OVERLAP: int = 64
    
    # 检索配置
    RETRIEVAL_TOP_K: int = 5
    DENSE_WEIGHT: float = 0.5
    BM25_WEIGHT: float = 0.5
    RRF_K: int = 60
    
    # 大模型配置 - 模式选择
    LLM_MODE: str = "api"  # "local" 或 "api"
    
    # 本地模型配置（LLM_MODE=local 时使用）
    LOCAL_LLM_PATH: Optional[str] = None  # 本地模型路径
    LOCAL_LLM_URL: str = "http://localhost:1234/v1"  # LM Studio 默认地址
    
    # 在线 API 配置（LLM_MODE=api 时使用）
    # 通义千问
    DASHSCOPE_API_KEY: Optional[str] = None
    DASHSCOPE_MODEL: str = "qwen-turbo"
    
    # 文心一言（备选）
    ERNIE_API_KEY: Optional[str] = None
    ERNIE_SECRET_KEY: Optional[str] = None
    
    # OpenAI 兼容接口（LM Studio / Ollama）
    OPENAI_API_BASE: str = "http://localhost:1234/v1"
    OPENAI_API_KEY: str = "not-needed"
    OPENAI_MODEL: str = "local-model"
    
    # 大模型生成参数
    LLM_TEMPERATURE: float = 0.3
    LLM_TOP_P: float = 0.9
    LLM_MAX_TOKENS: int = 2048
    LLM_TIMEOUT: int = 60  # 秒
    
    # 稳定性配置
    RATE_LIMIT_RPS: int = 10  # 每秒请求限制
    MAX_RETRY: int = 2  # 大模型调用重试次数
    
    # 幻觉检测配置
    HALLUCINATION_THRESHOLD: float = 0.5  # 相似度低于此值标记为幻觉
    
    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """获取配置单例"""
    return Settings()


# 全局配置实例
settings = get_settings()


# 快捷配置检查
def check_config():
    """检查配置是否有效"""
    errors = []
    
    if settings.LLM_MODE == "api" and not settings.DASHSCOPE_API_KEY:
        errors.append("API 模式需要设置 DASHSCOPE_API_KEY 或 ERNIE_API_KEY")
    
    if settings.LLM_MODE == "local" and not settings.LOCAL_LLM_PATH:
        errors.append("本地模式建议设置 LOCAL_LLM_PATH")
    
    if errors:
        print("配置检查失败:")
        for error in errors:
            print(f"  - {error}")
        return False
    
    print("配置检查通过 ✓")
    return True


if __name__ == "__main__":
    # 测试配置加载
    print(f"应用名称: {settings.APP_NAME}")
    print(f"LLM 模式: {settings.LLM_MODE}")
    print(f"向量库: Milvus@{settings.MILVUS_HOST}:{settings.MILVUS_PORT}")
    print(f"Embedding: {settings.EMBEDDING_MODEL}")
    check_config()
