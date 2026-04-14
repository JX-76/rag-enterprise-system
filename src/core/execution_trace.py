from __future__ import annotations

"""Structured execution trace models for query/task handling."""

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional
import time


@dataclass
class StageTrace:
    stage: str
    started_at_ms: float
    ended_at_ms: Optional[float] = None
    latency_ms: Optional[float] = None
    status: str = "started"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def finish(self, status: str = "ok", **metadata: Any) -> None:
        self.ended_at_ms = time.time() * 1000
        self.latency_ms = round(self.ended_at_ms - self.started_at_ms, 3)
        self.status = status
        if metadata:
            self.metadata.update(metadata)

    def fail(self, error: str) -> None:
        self.finish(status="error", error=error)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ExecutionTrace:
    trace_id: str
    route: Dict[str, Any]
    stages: List[StageTrace] = field(default_factory=list)
    fallback_triggered: bool = False
    notes: List[str] = field(default_factory=list)

    def add_stage(self, stage: StageTrace) -> None:
        self.stages.append(stage)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "route": self.route,
            "fallback_triggered": self.fallback_triggered,
            "notes": self.notes,
            "stages": [s.to_dict() for s in self.stages],
        }
