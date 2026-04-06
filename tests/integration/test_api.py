"""
Integration Tests for API - API集成测试
"""
import pytest
import asyncio
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, AsyncMock

# 假设main.py中创建了FastAPI app
# from src.main import app


class TestHealthEndpoint:
    """测试健康检查端点"""
    
    def test_health_check(self, client):
        """测试健康检查"""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data
        assert "timestamp" in data
    
    def test_health_ready(self, client):
        """测试就绪检查"""
        response = client.get("/health/ready")
        
        assert response.status_code == 200
        data = response.json()
        assert data["ready"] == True


class TestQueryEndpoint:
    """测试查询端点"""
    
    def test_query_success(self, client, mock_rag_engine):
        """测试成功查询"""
        with patch('src.api.routes.query.RAGService') as mock_service:
            mock_service.get_instance.return_value = mock_rag_engine
            
            response = client.post(
                "/api/v1/query",
                json={
                    "query": "什么是RAG？",
                    "top_k": 5,
                    "rewrite": True,
                    "rerank": True
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "answer" in data
            assert "sources" in data
            assert "latency_ms" in data
    
    def test_query_validation_error(self, client):
        """测试参数校验错误"""
        response = client.post(
            "/api/v1/query",
            json={
                "query": "",  # 空查询
                "top_k": 100  # 超过限制
            }
        )
        
        assert response.status_code == 422
    
    def test_query_rate_limit(self, client):
        """测试限流"""
        # 快速发送多个请求触发限流
        responses = []
        for _ in range(10):
            response = client.post(
                "/api/v1/query",
                json={"query": "测试"}
            )
            responses.append(response)
        
        # 至少有一个请求被限流
        assert any(r.status_code == 429 for r in responses)


class TestRetrieveEndpoint:
    """测试检索端点"""
    
    def test_retrieve_only(self, client, mock_rag_engine):
        """测试仅检索"""
        with patch('src.api.routes.query.RAGService') as mock_service:
            mock_service.get_instance.return_value = mock_rag_engine
            
            response = client.post(
                "/api/v1/retrieve",
                json={
                    "query": "RAG优化",
                    "top_k": 10
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "results" in data
            assert isinstance(data["results"], list)


class TestTracing:
    """测试链路追踪"""
    
    def test_trace_id_header(self, client):
        """测试TraceID响应头"""
        response = client.get("/health")
        
        assert "X-Request-ID" in response.headers
        assert len(response.headers["X-Request-ID"]) == 32
    
    def test_custom_trace_id(self, client):
        """测试自定义TraceID"""
        custom_id = "custom_trace_id_12345"
        response = client.get(
            "/health",
            headers={"X-Request-ID": custom_id}
        )
        
        assert response.headers["X-Request-ID"] == custom_id


class TestErrorHandling:
    """测试错误处理"""
    
    def test_not_found(self, client):
        """测试404"""
        response = client.get("/nonexistent")
        assert response.status_code == 404
        
        data = response.json()
        assert "error" in data
        assert "request_id" in data
    
    def test_method_not_allowed(self, client):
        """测试405"""
        response = client.post("/health")  # GET端点用POST
        assert response.status_code == 405


# Fixtures
@pytest.fixture
def client():
    """创建测试客户端"""
    # from src.main import app
    # return TestClient(app)
    pass  # 需要实际的app实例


@pytest.fixture
def mock_rag_engine():
    """创建mock RAG引擎"""
    engine = AsyncMock()
    engine.query = AsyncMock(return_value={
        "query": "什么是RAG？",
        "answer": "RAG是检索增强生成...",
        "sources": [
            {
                "id": "doc1",
                "content": "RAG相关内容",
                "score": 0.95,
                "metadata": {}
            }
        ],
        "rewritten_queries": ["RAG定义", "检索增强生成"],
        "latency_ms": 150.5
    })
    engine.retrieve = AsyncMock(return_value=[
        {"id": "doc1", "content": "内容1", "score": 0.9},
        {"id": "doc2", "content": "内容2", "score": 0.8},
    ])
    return engine


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
