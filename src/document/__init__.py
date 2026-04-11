"""Legacy document package kept for compatibility; prefer `src.ingestion` as the canonical parsing/chunking path."""
from .parser import DocumentParser, ParseError
from .chunker import SemanticChunker, TextChunk

__all__ = ['DocumentParser', 'ParseError', 'SemanticChunker', 'TextChunk']
