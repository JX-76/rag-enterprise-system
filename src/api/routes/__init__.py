"""API route package exports.

This package intentionally shadows the legacy ``src/api/routes.py`` module so
imports like ``from src.api.routes import query, retrieval, health`` resolve to
these maintained route modules.
"""

from . import health, query, retrieval

__all__ = ["health", "query", "retrieval"]
