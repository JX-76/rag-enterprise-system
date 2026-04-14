import pytest

from src.core.query_router import LightweightQueryRouter


class TestLightweightQueryRouter:
    def setup_method(self):
        self.router = LightweightQueryRouter()

    def test_route_exact_lookup(self):
        decision = self.router.route("官方 API 入口是什么？")
        assert decision.task_type == "exact_lookup"
        assert decision.rewrite_enabled is False
        assert decision.rerank_enabled is True

    def test_route_action_request(self):
        decision = self.router.route("帮我创建一个部署任务并执行")
        assert decision.task_type == "action_request"
        assert decision.tool_candidate is True
        assert decision.route == "tool_or_workflow_candidate"

    def test_route_summarization(self):
        decision = self.router.route("总结一下这个项目的整体架构和 trade-off")
        assert decision.task_type == "summarization"
        assert decision.recommended_top_k >= 8

    def test_route_complex_reasoning(self):
        decision = self.router.route("为什么这个系统需要 query rewrite、hybrid retrieval 和 reranker 一起配合？")
        assert decision.task_type in {"complex_reasoning", "summarization"}
        assert decision.rewrite_enabled is True
