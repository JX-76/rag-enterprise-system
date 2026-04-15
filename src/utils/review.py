"""Helpers for visualizing trace and lightweight review output."""
from __future__ import annotations

from typing import Any, Dict, List


def summarize_trace(trace: Dict[str, Any]) -> Dict[str, Any]:
    stages = trace.get("stages", []) or []
    sorted_stages = sorted(
        stages,
        key=lambda s: (s.get("latency_ms") or 0),
        reverse=True,
    )
    slowest_stage = sorted_stages[0] if sorted_stages else {}
    return {
        "trace_id": trace.get("trace_id"),
        "fallback_triggered": trace.get("fallback_triggered", False),
        "notes": trace.get("notes", []),
        "stage_count": len(stages),
        "slowest_stage": {
            "stage": slowest_stage.get("stage"),
            "latency_ms": slowest_stage.get("latency_ms"),
            "status": slowest_stage.get("status"),
        } if slowest_stage else None,
        "stages": [
            {
                "stage": s.get("stage"),
                "status": s.get("status"),
                "latency_ms": s.get("latency_ms"),
                "metadata_keys": sorted(list((s.get("metadata") or {}).keys())),
            }
            for s in stages
        ],
    }


def build_review_view(result: Dict[str, Any]) -> Dict[str, Any]:
    trace = result.get("trace", {}) or {}
    route = result.get("route", {}) or {}
    support = result.get("support", {}) or {}
    sources = result.get("sources", []) or []
    trace_summary = summarize_trace(trace)

    suspicion_flags = []
    if support.get("confidence", 0.0) < 0.5:
        suspicion_flags.append("low_support_confidence")
    if support.get("has_support") is False:
        suspicion_flags.append("fallback_or_no_support")
    if trace_summary.get("fallback_triggered"):
        suspicion_flags.append("fallback_triggered")
    if trace_summary.get("slowest_stage", {}).get("latency_ms", 0) and trace_summary["slowest_stage"]["latency_ms"] > 500:
        suspicion_flags.append("slow_stage_detected")

    return {
        "query": result.get("query"),
        "answer_preview": (result.get("answer") or "")[:200],
        "route": {
            "task_type": route.get("task_type"),
            "route": route.get("route"),
            "confidence": route.get("confidence"),
            "reasons": route.get("reasons", []),
        },
        "support": support,
        "sources_count": len(sources),
        "top_sources": [
            {
                "id": s.get("id"),
                "score": s.get("score"),
                "metadata": s.get("metadata", {}),
            }
            for s in sources[:3]
        ],
        "trace_summary": trace_summary,
        "suspicion_flags": suspicion_flags,
    }
