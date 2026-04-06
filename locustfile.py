"""
Locust压测脚本
测试RAG API性能
"""
from locust import HttpUser, task, between
import random


class RAGUser(HttpUser):
    """模拟RAG API用户"""
    wait_time = between(1, 5)
    
    def on_start(self):
        """每个用户启动时执行"""
        # 健康检查
        self.client.get("/health")
    
    @task(3)
    def health_check(self):
        """健康检查 - 高频"""
        self.client.get("/health")
    
    @task(2)
    def query_simple(self):
        """简单查询"""
        queries = [
            "什么是机器学习？",
            "什么是深度学习？",
            "什么是人工智能？",
            "RAG是什么？",
            "如何优化向量检索？",
        ]
        payload = {
            "query": random.choice(queries),
            "top_k": 5,
            "enable_rewrite": False
        }
        with self.client.post("/query", json=payload, catch_response=True) as response:
            if response.status_code == 200:
                data = response.json()
                if "answer" in data:
                    response.success()
                else:
                    response.failure("Missing answer in response")
            else:
                response.failure(f"Status code: {response.status_code}")
    
    @task(1)
    def query_with_rewrite(self):
        """带改写的查询 - 耗时更长"""
        payload = {
            "query": "机器学习在工业界的应用",
            "top_k": 10,
            "enable_rewrite": True
        }
        with self.client.post("/query", json=payload, catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Status code: {response.status_code}")
    
    @task(1)
    def ingest_document(self):
        """接入文档"""
        payload = {
            "content": """
            # 人工智能简介
            
            人工智能（AI）是计算机科学的一个分支。
            机器学习是AI的核心技术之一。
            深度学习使用多层神经网络。
            """,
            "metadata": {"source": "test", "type": "markdown"},
            "chunking_strategy": "parent_child"
        }
        self.client.post("/ingest", json=payload)


class ReadOnlyUser(HttpUser):
    """只读用户"""
    wait_time = between(0.5, 2)
    
    @task
    def read_endpoints(self):
        """只访问只读端点"""
        endpoints = ["/health", "/ready", "/config"]
        self.client.get(random.choice(endpoints))
