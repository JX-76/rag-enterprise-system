"""Retrieval filters for ACL / metadata-aware retrieval."""

from __future__ import annotations

from dataclasses import dataclass, asdict, field
from typing import Any, Dict, List, Optional


@dataclass
class RetrievalAccessContext:
    tenant_id: Optional[str] = None
    role: Optional[str] = None
    allowed_doc_ids: List[str] = field(default_factory=list)
    metadata_filters: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class RetrievalFilterEngine:
    """Apply lightweight ACL / metadata filtering on retrieval results."""

    def build_filter_dict(self, access_context: Optional[RetrievalAccessContext]) -> Dict[str, Any]:
        if not access_context:
            return {}
        filter_dict = dict(access_context.metadata_filters or {})
        if access_context.tenant_id:
            filter_dict.setdefault("tenant_id", access_context.tenant_id)
        if access_context.role:
            filter_dict.setdefault("role", access_context.role)
        return filter_dict

    def filter_results(
        self,
        results: List[Dict[str, Any]],
        access_context: Optional[RetrievalAccessContext] = None,
    ) -> List[Dict[str, Any]]:
        if not access_context:
            return results

        filtered = []
        allowed_doc_ids = set(access_context.allowed_doc_ids or [])
        filter_dict = self.build_filter_dict(access_context)

        for result in results:
            metadata = result.get("metadata", {}) or {}

            if allowed_doc_ids and result.get("id") not in allowed_doc_ids and metadata.get("doc_id") not in allowed_doc_ids:
                continue

            if filter_dict:
                matched = True
                for key, value in filter_dict.items():
                    if metadata.get(key) != value:
                        matched = False
                        break
                if not matched:
                    continue

            filtered.append(result)

        return filtered
