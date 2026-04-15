"""API route package exports.

This package intentionally shadows the legacy ``src/api/routes.py`` module so
imports like ``from src.api.routes import query, retrieval, health, evaluation`` resolve to
these maintained route modules.
"""

from . import evaluation, health, query, retrieval

__all__ = ["health", "query", "retrieval", "evaluation"]
