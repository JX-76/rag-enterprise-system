"""API package.

Avoid eager FastAPI route imports here so low-level modules (e.g. middleware)
can be imported in lightweight test environments without requiring FastAPI.
"""

__all__ = []
