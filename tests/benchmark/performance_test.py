"""
Performance Benchmark Tests - 性能基准测试
"""
import pytest
import asyncio
import time
import statistics
from concurrent.futures import ThreadPoolExecutor
import requests
from typing import List, Dict


class TestQueryLatency:
    """查询延迟测试"""
    
    @pytest.mark.benchmark
    def test_single_query_latency(self, base_url):
        """测试单次查询延迟"""
        latencies = []
        
        for _ in range(10):
            start = time.time()
            response = requests.post(
                f"{base_url}/api/v1/query",
                json={"query": "RAG优化方法", "top_k": 5}
            )
            latency = (time.time() - start) * 1000
            latencies.append(latency)
            
            assert response.status_code == 200
        
        avg_latency = statistics.mean(latencies)
        p99_latency = sorted(latencies)[int(len(latencies) * 0.99)]
        
        print(f"\n单查询延迟:")
        print(f"  平均: {avg_latency:.2f}ms")
        print(f"  P99: {p99_latency:.2f}ms")
        
        # 断言性能指标
        assert avg_latency < 500, f"平均延迟过高: {avg_latency}ms"
        assert p99_latency < 1000, f"P99延迟过高: {p99_latency}ms"
    
    @pytest.mark.benchmark
    def test_concurrent_query_latency(self, base_url):
        """测试并发查询延迟"""
        def make_request():
            start = time.time()
            response = requests.post(
                f"{base_url}/api/v1/query",
                json={"query": "什么是RAG系统"}
            )
            latency = (time.time() - start) * 1000
            return response.status_code, latency
        
        # 并发10个请求
        with ThreadPoolExecutor(max_workers=10) as executor:
            results = list(executor.map(lambda _: make_request(), range(10)))
        
        latencies = [r[1] for r in results]
        avg_latency = statistics.mean(latencies)
        max_latency = max(latencies)
        
        print(f"\n并发查询延迟 (10并发):")
        print(f"  平均: {avg_latency:.2f}ms")
        print(f"  最大: {max_latency:.2f}ms")
        
        assert avg_latency < 1000


class TestThroughput:
    """吞吐量测试"""
    
    @pytest.mark.benchmark
    def test_queries_per_second(self, base_url):
        """测试QPS"""
        duration = 10  # 测试10秒
        query_count = 0
        errors = 0
        
        start_time = time.time()
        
        while time.time() - start_time < duration:
            try:
                response = requests.post(
                    f"{base_url}/api/v1/query",
                    json={"query": "RAG优化"},
                    timeout=5
                )
                if response.status_code == 200:
                    query_count += 1
                else:
                    errors += 1
            except Exception as e:
                errors += 1
        
        elapsed = time.time() - start_time
        qps = query_count / elapsed
        
        print(f"\n吞吐量测试 ({duration}秒):")
        print(f"  总请求: {query_count}")
        print(f"  失败: {errors}")
        print(f"  QPS: {qps:.2f}")
        print(f"  成功率: {(query_count / (query_count + errors)) * 100:.1f}%")
        
        assert qps > 10, f"QPS过低: {qps}"
        assert errors / (query_count + errors) < 0.05, "错误率过高"


class TestRetrievalPerformance:
    """检索性能测试"""
    
    @pytest.mark.benchmark
    def test_retrieval_only_speed(self, base_url):
        """测试纯检索速度"""
        latencies = []
        
        for _ in range(20):
            start = time.time()
            response = requests.post(
                f"{base_url}/api/v1/retrieve",
                json={"query": "混合检索", "top_k": 10}
            )
            latency = (time.time() - start) * 1000
            latencies.append(latency)
            
            assert response.status_code == 200
        
        avg = statistics.mean(latencies)
        p95 = sorted(latencies)[int(len(latencies) * 0.95)]
        
        print(f"\n纯检索性能:")
        print(f"  平均: {avg:.2f}ms")
        print(f"  P95: {p95:.2f}ms")
        
        # 纯检索应该更快
        assert avg < 200, f"检索延迟过高: {avg}ms"


class TestMemoryUsage:
    """内存使用测试"""
    
    @pytest.mark.benchmark
    def test_memory_stability(self, base_url):
        """测试内存稳定性"""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        
        # 记录初始内存
        initial_mem = process.memory_info().rss / 1024 / 1024  # MB
        
        # 发送大量请求
        for i in range(100):
            response = requests.post(
                f"{base_url}/api/v1/query",
                json={"query": f"查询{i}"}
            )
        
        # 记录最终内存
        final_mem = process.memory_info().rss / 1024 / 1024  # MB
        
        print(f"\n内存使用:")
        print(f"  初始: {initial_mem:.1f}MB")
        print(f"  最终: {final_mem:.1f}MB")
        print(f"  增长: {final_mem - initial_mem:.1f}MB")
        
        # 内存增长不应过大（可能存在内存泄漏）
        assert final_mem - initial_mem < 100, "内存泄漏警告"


class TestRetrievalQuality:
    """检索质量测试"""
    
    @pytest.mark.benchmark
    def test_recall_at_k(self, base_url, test_queries):
        """测试Recall@K"""
        recalls = []
        
        for query_data in test_queries:
            query = query_data["query"]
            relevant_docs = set(query_data["relevant_docs"])
            
            response = requests.post(
                f"{base_url}/api/v1/retrieve",
                json={"query": query, "top_k": 20}
            )
            
            if response.status_code == 200:
                results = response.json()["results"]
                retrieved_ids = {r["id"] for r in results}
                
                # 计算Recall@20
                if relevant_docs:
                    recall = len(relevant_docs & retrieved_ids) / len(relevant_docs)
                    recalls.append(recall)
        
        avg_recall = statistics.mean(recalls) if recalls else 0
        
        print(f"\n检索质量:")
        print(f"  Recall@20: {avg_recall * 100:.1f}%")
        print(f"  测试用例: {len(recalls)}")
        
        assert avg_recall > 0.7, f"Recall@20过低: {avg_recall}"


# Fixtures
@pytest.fixture
def base_url():
    """API基础URL"""
    return "http://localhost:8000"


@pytest.fixture
def test_queries():
    """测试查询集"""
    return [
        {
            "query": "RAG优化方法",
            "relevant_docs": ["doc1", "doc2", "doc3"]
        },
        {
            "query": "向量检索原理",
            "relevant_docs": ["doc4", "doc5"]
        },
    ]


if __name__ == "__main__":
    # 运行基准测试
    pytest.main([__file__, "-v", "-m", "benchmark"])
