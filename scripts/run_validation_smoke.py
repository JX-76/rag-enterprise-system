#!/usr/bin/env python3
"""Run a no-server validation smoke flow and persist outputs."""
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from src.main import app

ARTIFACT_DIR = ROOT / "artifacts" / "eval"
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)


def mock_query_result():
    return {
        "query": "系统支持哪些检索优化能力？",
        "answer": "支持 hybrid retrieval、query rewrite、rerank 和 support-aware fallback。",
        "sources": [
            {
                "id": "doc_hybrid_retrieval",
                "content": "Hybrid Retrieval combines dense and sparse retrieval.",
                "score": 0.93,
                "metadata": {"section": "retrieval"},
            }
        ],
        "rewritten_queries": ["检索优化能力", "hybrid retrieval 能力"],
        "latency_ms": 128.4,
        "route": {
            "task_type": "knowledge_qa",
            "route": "retrieve_then_answer",
            "confidence": 0.82,
            "reasons": ["Defaulted to knowledge QA path."],
            "rewrite_enabled": True,
            "rerank_enabled": True,
            "recommended_top_k": 5,
            "tool_candidate": False,
        },
        "support": {
            "has_support": True,
            "confidence": 0.74,
            "reason": "retrieval_backed_generation",
            "citations_count": 1,
        },
        "trace": {
            "trace_id": "trace_smoke_run",
            "route": {"task_type": "knowledge_qa"},
            "fallback_triggered": False,
            "notes": [],
            "stages": [
                {"stage": "retrieve", "status": "ok", "latency_ms": 121.0, "metadata": {"results_count": 1}},
                {"stage": "generate", "status": "ok", "latency_ms": 82.0, "metadata": {"context_count": 1}},
            ],
        },
    }


def write_artifact(name: str, payload: dict) -> Path:
    path = ARTIFACT_DIR / name
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def main() -> None:
    client = TestClient(app)
    mocked_engine = AsyncMock()
    mocked_engine.query = AsyncMock(return_value=mock_query_result())

    fake_report = {
        "meta": {"validation_level": "lightweight", "note": "smoke-script"},
        "retrieval": {"recall@20": 0.0, "precision@3": 0.0, "ndcg@10": 0.0, "mrr": 0.0, "map": 0.0},
        "generation": {"avg_faithfulness": 0.0, "avg_relevance": 0.0, "avg_hallucination": 0.0},
        "performance": {"avg_latency_ms": 0.0, "p99_latency_ms": 0.0, "p95_latency_ms": 0.0, "avg_support_confidence": 0.0, "fallback_rate": 0.0},
        "details": {"badcases": []},
    }

    with patch("src.api.routes.query.RAGService.get_instance", return_value=mocked_engine), \
         patch("src.api.routes.evaluation.BenchmarkRunner") as mock_runner_cls:
        mock_runner = AsyncMock()
        mock_runner.run_benchmark = AsyncMock(return_value=fake_report)
        mock_runner_cls.return_value = mock_runner

        review = client.post("/api/v1/query/review", json={"query": "系统支持哪些检索优化能力？", "top_k": 5, "rewrite": True, "rerank": True})
        trace = client.post("/api/v1/query/trace-summary", json={"query": "系统支持哪些检索优化能力？", "top_k": 5, "rewrite": True, "rerank": True})
        eval_resp = client.post("/api/v1/eval/lightweight", json={"note": "smoke-script", "persist_artifact": False, "dataset": [{"query": "系统支持哪些检索优化能力？", "relevant_docs": ["doc_hybrid_retrieval"]}]})
        badcases = client.post("/api/v1/eval/badcases", json={"note": "smoke-script", "persist_artifact": False, "dataset": [{"query": "系统支持哪些检索优化能力？", "relevant_docs": ["doc_hybrid_retrieval"]}]})

    outputs = {
        "review": review.json(),
        "trace_summary": trace.json(),
        "lightweight_eval": eval_resp.json(),
        "badcases": badcases.json(),
    }

    summary = {
        "review_path": str(write_artifact("smoke_review_output.json", outputs["review"])),
        "trace_path": str(write_artifact("smoke_trace_output.json", outputs["trace_summary"])),
        "eval_path": str(write_artifact("smoke_eval_output.json", outputs["lightweight_eval"])),
        "badcases_path": str(write_artifact("smoke_badcases_output.json", outputs["badcases"])),
    }

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
