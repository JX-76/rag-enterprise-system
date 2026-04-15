import json
import sys
from pathlib import Path
from unittest.mock import patch, AsyncMock

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from src.main import app


def _mock_query_result():
    return {
        "query": "系统支持哪些检索优化能力？",
        "answer": "支持 hybrid retrieval、query rewrite 和 rerank。",
        "sources": [
            {
                "id": "doc_hybrid_retrieval",
                "content": "Hybrid Retrieval combines dense and sparse search.",
                "score": 0.92,
                "metadata": {"section": "retrieval"},
            }
        ],
        "rewritten_queries": ["检索优化能力", "hybrid retrieval 能力"],
        "latency_ms": 123.4,
        "route": {
            "task_type": "knowledge_qa",
            "route": "retrieve_then_answer",
            "confidence": 0.8,
            "reasons": ["Defaulted to knowledge QA path."],
            "rewrite_enabled": True,
            "rerank_enabled": True,
            "recommended_top_k": 5,
            "tool_candidate": False,
        },
        "support": {
            "has_support": True,
            "confidence": 0.72,
            "reason": "retrieval_backed_generation",
            "citations_count": 1,
        },
        "trace": {
            "trace_id": "trace_test_1",
            "route": {"task_type": "knowledge_qa"},
            "fallback_triggered": False,
            "notes": [],
            "stages": [
                {
                    "stage": "retrieve",
                    "status": "ok",
                    "latency_ms": 120.0,
                    "metadata": {"results_count": 1},
                },
                {
                    "stage": "generate",
                    "status": "ok",
                    "latency_ms": 80.0,
                    "metadata": {"context_count": 1},
                },
            ],
        },
    }


def test_query_review_endpoint_returns_visual_review():
    client = TestClient(app)
    mocked_engine = AsyncMock()
    mocked_engine.query = AsyncMock(return_value=_mock_query_result())

    with patch("src.api.routes.query.RAGService.get_instance", return_value=mocked_engine):
        response = client.post(
            "/api/v1/query/review",
            json={"query": "系统支持哪些检索优化能力？", "top_k": 5, "rewrite": True, "rerank": True},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["query"] == "系统支持哪些检索优化能力？"
    assert "trace_summary" in data
    assert "suspicion_flags" in data
    assert data["trace_summary"]["slowest_stage"]["stage"] == "retrieve"


def test_trace_summary_endpoint_returns_slowest_stage():
    client = TestClient(app)
    mocked_engine = AsyncMock()
    mocked_engine.query = AsyncMock(return_value=_mock_query_result())

    with patch("src.api.routes.query.RAGService.get_instance", return_value=mocked_engine):
        response = client.post(
            "/api/v1/query/trace-summary",
            json={"query": "系统支持哪些检索优化能力？", "top_k": 5, "rewrite": True, "rerank": True},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["trace_id"] == "trace_test_1"
    assert data["slowest_stage"]["stage"] == "retrieve"


def test_lightweight_eval_persists_artifact(tmp_path: Path):
    client = TestClient(app)
    fake_report = {
        "meta": {"validation_level": "lightweight"},
        "details": {"badcases": []},
        "retrieval": {},
        "generation": {},
        "performance": {},
    }

    with patch("src.api.routes.evaluation.ARTIFACT_DIR", tmp_path), \
         patch("src.api.routes.evaluation.BenchmarkRunner") as mock_runner_cls:
        mock_runner = AsyncMock()
        mock_runner.run_benchmark = AsyncMock(return_value=fake_report)
        mock_runner_cls.return_value = mock_runner

        response = client.post(
            "/api/v1/eval/lightweight",
            json={
                "note": "smoke",
                "persist_artifact": True,
                "dataset": [
                    {"query": "系统支持哪些检索优化能力？", "relevant_docs": ["doc_hybrid_retrieval"]}
                ],
            },
        )

    assert response.status_code == 200
    data = response.json()
    artifact_path = data["meta"]["artifact_path"]
    assert Path(artifact_path).exists()
    saved = json.loads(Path(artifact_path).read_text(encoding="utf-8"))
    assert saved["meta"]["note"] == "smoke"
