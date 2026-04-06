"""
Monitoring & Metrics - 监控指标
"""
from prometheus_client import Counter, Histogram, Gauge, Info
from typing import Optional


class MetricsCollector:
    """指标收集器"""
    
    def __init__(self):
        # 请求计数
        self.request_count = Counter(
            'rag_requests_total',
            'Total requests',
            ['endpoint', 'status']
        )
        
        # 请求延迟
        self.request_latency = Histogram(
            'rag_request_duration_seconds',
            'Request duration in seconds',
            ['endpoint'],
            buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
        )
        
        # 检索相关
        self.retrieval_latency = Histogram(
            'rag_retrieval_duration_seconds',
            'Retrieval duration',
            buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25]
        )
        
        self.retrieval_results = Gauge(
            'rag_retrieval_results',
            'Number of retrieval results'
        )
        
        # 重排序
        self.rerank_latency = Histogram(
            'rag_rerank_duration_seconds',
            'Rerank duration',
            buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25]
        )
        
        # 生成
        self.generation_latency = Histogram(
            'rag_generation_duration_seconds',
            'Generation duration',
            buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0]
        )
        
        # 应用信息
        self.app_info = Info('rag_app', 'Application info')
        self.app_info.info({'version': '1.0.0'})
    
    def record_request(self, endpoint: str, status_code: int, duration_ms: float):
        """记录请求指标"""
        status = str(status_code)
        self.request_count.labels(endpoint=endpoint, status=status).inc()
        self.request_latency.labels(endpoint=endpoint).observe(duration_ms / 1000)


# 全局指标实例
metrics = MetricsCollector()
