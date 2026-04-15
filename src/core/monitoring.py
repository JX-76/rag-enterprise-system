"""
Monitoring & Metrics - 监控指标
"""
from typing import Optional

from prometheus_client import Counter, Gauge, Histogram, Info


class MetricsCollector:
    """指标收集器"""

    def __init__(self):
        self.request_count = Counter(
            'rag_requests_total',
            'Total requests',
            ['endpoint', 'status']
        )

        self.request_latency = Histogram(
            'rag_request_duration_seconds',
            'Request duration in seconds',
            ['endpoint'],
            buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
        )

        self.retrieval_latency = Histogram(
            'rag_retrieval_duration_seconds',
            'Retrieval duration',
            buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25]
        )

        self.retrieval_results = Gauge(
            'rag_retrieval_results',
            'Number of retrieval results'
        )

        self.rerank_latency = Histogram(
            'rag_rerank_duration_seconds',
            'Rerank duration',
            buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25]
        )

        self.generation_latency = Histogram(
            'rag_generation_duration_seconds',
            'Generation duration',
            buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0]
        )

        self.route_decisions = Counter(
            'rag_route_decisions_total',
            'Route decisions by task type and route',
            ['task_type', 'route']
        )

        self.fallback_count = Counter(
            'rag_fallback_total',
            'Total fallback responses',
            ['reason']
        )

        self.support_confidence = Gauge(
            'rag_support_confidence',
            'Support confidence of latest response'
        )

        self.evaluation_runs = Counter(
            'rag_evaluation_runs_total',
            'Total evaluation runs'
        )

        self.evaluation_dataset_size = Gauge(
            'rag_evaluation_dataset_size',
            'Dataset size of the latest evaluation run'
        )

        self.app_info = Info('rag_app', 'Application info')
        self.app_info.info({'version': '1.0.0'})

    def record_request(self, endpoint: str, status_code: int, duration_ms: float):
        status = str(status_code)
        self.request_count.labels(endpoint=endpoint, status=status).inc()
        self.request_latency.labels(endpoint=endpoint).observe(duration_ms / 1000)

    def record_route(self, task_type: str, route: str):
        self.route_decisions.labels(task_type=task_type, route=route).inc()

    def record_fallback(self, reason: str):
        self.fallback_count.labels(reason=reason).inc()

    def record_support_confidence(self, confidence: float):
        self.support_confidence.set(confidence)

    def record_evaluation_run(self, dataset_size: int):
        self.evaluation_runs.inc()
        self.evaluation_dataset_size.set(dataset_size)


metrics = MetricsCollector()
