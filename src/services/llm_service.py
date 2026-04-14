"""
LLM Service - lightweight async service wrapper for project generation paths.

This file provides the async interface expected by:
- src/generation/generator.py
- src/core/agentic_rag.py

It intentionally keeps a small, project-safe surface:
- get_llm_service()
- AsyncLLMService.generate(...)
- AsyncLLMService.generate_stream(...)
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Dict, Optional

from src.core.config import settings
from src.core.logging import get_logger
from . import __all__  # noqa: F401  # keep package import side-effects minimal

logger = get_logger(__name__)


@dataclass
class LLMResponse:
    """Async service response expected by generator / agentic modules."""

    content: str
    provider: str = "mock"
    model: str = "mock-llm"
    tokens_prompt: int = 0
    tokens_completion: int = 0
    fallback_used: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


class AsyncLLMService:
    """Small async-compatible LLM abstraction with safe mock fallback."""

    def __init__(self):
        self.model = getattr(settings, "LLM_MODEL", "mock-llm")
        self.provider = "mock"

    async def generate(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 512,
        fallback: bool = True,
        **_: Any,
    ) -> LLMResponse:
        """Generate a deterministic lightweight response.

        This is intentionally simple but matches the async interface already used
        elsewhere in the repo, preventing runtime import/interface mismatches.
        """
        await asyncio.sleep(0)

        prompt_tokens = max(1, len(prompt) // 4)
        synthesized = self._mock_answer(prompt, max_tokens=max_tokens)
        completion_tokens = max(1, len(synthesized) // 4)

        return LLMResponse(
            content=synthesized,
            provider=self.provider,
            model=self.model,
            tokens_prompt=prompt_tokens,
            tokens_completion=completion_tokens,
            fallback_used=fallback,
            metadata={
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
        )

    async def generate_stream(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 512,
        fallback: bool = True,
        chunk_size: int = 32,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        """Yield response chunks for SSE / streaming API usage."""
        response = await self.generate(
            prompt=prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            fallback=fallback,
            **kwargs,
        )
        text = response.content
        for i in range(0, len(text), chunk_size):
            await asyncio.sleep(0)
            yield text[i : i + chunk_size]

    def _mock_answer(self, prompt: str, max_tokens: int = 512) -> str:
        preview = prompt.replace("\n", " ")[: min(240, max_tokens)]
        if "无法回答" in prompt or "参考信息不足" in prompt:
            return "基于当前参考信息，我会优先给出有依据的结论；若证据不足，应返回低支持度结果并提示补充信息。"
        return f"基于提供的上下文，系统可返回结构化答案、引用来源、support 信号与 trace 元数据。摘要：{preview}"


_service_singleton: Optional[AsyncLLMService] = None


def get_llm_service() -> AsyncLLMService:
    global _service_singleton
    if _service_singleton is None:
        _service_singleton = AsyncLLMService()
        logger.info("Initialized async LLM service wrapper")
    return _service_singleton
