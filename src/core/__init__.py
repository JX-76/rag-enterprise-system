"""Core package.

Avoid eager imports here so utility modules (metrics/logging/config) remain
usable in lightweight environments without pulling the whole engine graph.
"""

__all__ = []
