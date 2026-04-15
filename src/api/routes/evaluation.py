"""Evaluation routes for lightweight validation, badcase review and report persistence."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.core.rag_engine import RAGEngine
from src.evaluation.metrics import BenchmarkRunner

router = APIRouter()
ARTIFACT_DIR = Path("artifacts/eval")


class EvalItem(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000)
    relevant_docs: List[str] = Field(default_factory=list)


class EvalRequest(BaseModel):
    dataset: List[EvalItem] = Field(..., min_length=1, max_length=100)
    note: Optional[str] = Field(None, description="本次轻量验证备注")
    persist_artifact: bool = Field(True, description="是否将结果写入 artifacts/eval")


def _artifact_path(prefix: str) -> Path:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return ARTIFACT_DIR / f"{prefix}_{timestamp}.json"


def _persist(prefix: str, payload: Dict[str, Any]) -> str:
    path = _artifact_path(prefix)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


@router.post("/lightweight")
async def run_lightweight_evaluation(req: EvalRequest) -> Dict[str, Any]:
    try:
        runner = BenchmarkRunner(RAGEngine())
        dataset = [item.model_dump() for item in req.dataset]
        report = await runner.run_benchmark(dataset)
        if req.note:
            report.setdefault("meta", {})["note"] = req.note
        if req.persist_artifact:
            report.setdefault("meta", {})["artifact_path"] = _persist("lightweight_eval", report)
        return report
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"lightweight evaluation failed: {exc}") from exc


@router.post("/badcases")
async def extract_badcases(req: EvalRequest) -> Dict[str, Any]:
    try:
        runner = BenchmarkRunner(RAGEngine())
        dataset = [item.model_dump() for item in req.dataset]
        report = await runner.run_benchmark(dataset)
        payload = {
            "meta": report.get("meta", {}),
            "badcases": report.get("details", {}).get("badcases", []),
            "badcase_count": len(report.get("details", {}).get("badcases", [])),
        }
        if req.note:
            payload.setdefault("meta", {})["note"] = req.note
        if req.persist_artifact:
            payload.setdefault("meta", {})["artifact_path"] = _persist("badcases", payload)
        return payload
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"badcase extraction failed: {exc}") from exc
