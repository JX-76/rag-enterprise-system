from __future__ import annotations

"""
Lightweight query/task router for production-oriented RAG.

Goal:
- distinguish knowledge lookup vs summarization vs action/tool-like queries
- provide a small, explainable routing layer without overclaiming full agent planning
- expose structured routing metadata for tracing and evaluation
"""

from dataclasses import dataclass, asdict
import re
from typing import List


@dataclass
class RoutingDecision:
    task_type: str
    route: str
    confidence: float
    reasons: List[str]
    rewrite_enabled: bool
    rerank_enabled: bool
    recommended_top_k: int
    tool_candidate: bool

    def to_dict(self) -> dict:
        return asdict(self)


class LightweightQueryRouter:
    """Heuristic router used as a low-cost execution boundary detector."""

    ACTION_PATTERNS = [
        r"\b(create|update|delete|deploy|execute|run|schedule|call api|invoke|fix)\b",
        r"(创建|修改|删除|部署|执行|调用|修复|新增|安排|调度)",
    ]
    SUMMARY_PATTERNS = [
        r"\b(summarize|summary|compare|overview|pros and cons|trade-?off)\b",
        r"(总结|概述|对比|比较|综述|优缺点|取舍|全景)",
    ]
    EXACT_LOOKUP_PATTERNS = [
        r"\b(api|endpoint|path|config|parameter|entrypoint|file|class|function)\b",
        r"(接口|入口|路径|配置|参数|文件|类|函数|脚本|文档)",
    ]
    MULTI_STEP_PATTERNS = [
        r"\b(why|how|root cause|debug|diagnose|investigate|step by step)\b",
        r"(为什么|怎么做|排查|定位|根因|逐步|步骤|原理)",
    ]

    def route(self, query: str) -> RoutingDecision:
        text = (query or "").strip()
        lowered = text.lower()
        reasons: List[str] = []

        if self._matches_any(text, lowered, self.ACTION_PATTERNS):
            reasons.append("Detected action-oriented intent; keep routing metadata for future tool execution.")
            return RoutingDecision(
                task_type="action_request",
                route="tool_or_workflow_candidate",
                confidence=0.81,
                reasons=reasons,
                rewrite_enabled=False,
                rerank_enabled=True,
                recommended_top_k=6,
                tool_candidate=True,
            )

        if self._matches_any(text, lowered, self.SUMMARY_PATTERNS):
            reasons.append("Detected summarization / comparison intent; widen retrieval context.")
            return RoutingDecision(
                task_type="summarization",
                route="retrieve_then_summarize",
                confidence=0.84,
                reasons=reasons,
                rewrite_enabled=True,
                rerank_enabled=True,
                recommended_top_k=8,
                tool_candidate=False,
            )

        if self._matches_any(text, lowered, self.EXACT_LOOKUP_PATTERNS):
            reasons.append("Detected exact lookup intent; avoid unnecessary rewrite noise.")
            return RoutingDecision(
                task_type="exact_lookup",
                route="retrieve_then_answer",
                confidence=0.78,
                reasons=reasons,
                rewrite_enabled=False,
                rerank_enabled=True,
                recommended_top_k=5,
                tool_candidate=False,
            )

        if self._matches_any(text, lowered, self.MULTI_STEP_PATTERNS) or len(text) >= 40:
            reasons.append("Detected complex or multi-step information need; enable rewrite and richer retrieval.")
            return RoutingDecision(
                task_type="complex_reasoning",
                route="retrieve_then_answer",
                confidence=0.73,
                reasons=reasons,
                rewrite_enabled=True,
                rerank_enabled=True,
                recommended_top_k=8,
                tool_candidate=False,
            )

        reasons.append("Defaulted to knowledge QA path.")
        return RoutingDecision(
            task_type="knowledge_qa",
            route="retrieve_then_answer",
            confidence=0.62,
            reasons=reasons,
            rewrite_enabled=True,
            rerank_enabled=True,
            recommended_top_k=5,
            tool_candidate=False,
        )

    @staticmethod
    def _matches_any(text: str, lowered: str, patterns: List[str]) -> bool:
        for pattern in patterns:
            if re.search(pattern, lowered, flags=re.IGNORECASE) or re.search(pattern, text):
                return True
        return False
