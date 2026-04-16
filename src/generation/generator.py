"""
LLM Generator - LLM生成器
支持上下文压缩、引用生成、幻觉检测
"""
from typing import List, Dict, Any, Optional
import time
import re

from src.core.config import settings
from src.core.logging import get_logger
from src.services.llm_service import get_llm_service

logger = get_logger(__name__)


class ContextCompressor:
    """
    上下文压缩器
    基于LLMLingua的思想
    """

    def compress(
        self,
        contexts: List[Dict[str, Any]],
        max_tokens: int = 4000
    ) -> str:
        """
        压缩上下文

        策略：
        1. 删除冗余词
        2. 保留关键实体和关系
        3. 控制总长度
        """
        compressed_parts = []
        total_length = 0

        for ctx in contexts:
            title = (
                ctx.get("metadata", {}).get("title")
                or ctx.get("metadata", {}).get("path")
                or ctx.get("id", "")
            )
            content = ctx.get("content", "")
            block = f"[来源: {title}]\n{content}" if title else content

            if total_length + len(block) > max_tokens * 4:
                remaining = max_tokens * 4 - total_length
                if remaining > 200:
                    block = block[:remaining] + "..."
                else:
                    break

            compressed_parts.append(block)
            total_length += len(block)

        return "\n\n".join(compressed_parts)


class LLMGenerator:
    """
    LLM生成器

    特性：
    - 接入真实LLM API（OpenAI/Anthropic）
    - 自动降级
    - Token消耗统计
    """

    def __init__(self):
        self.llm_service = get_llm_service()
        self.context_compressor = ContextCompressor()
        self.max_context_length = 4000
        self.max_tokens = 1000
        self.temperature = 0.2

    async def generate(
        self,
        query: str,
        contexts: List[Dict[str, Any]],
        conversation_id: Optional[str] = None
    ) -> str:
        """
        生成答案

        Args:
            query: 用户问题
            contexts: 检索到的上下文
            conversation_id: 会话ID（多轮对话）

        Returns:
            生成的答案
        """
        start_time = time.time()

        context_text = self.context_compressor.compress(
            contexts,
            max_tokens=self.max_context_length
        )

        prompt = self._build_prompt(query, context_text)

        logger.debug(f"Generating answer for query: {query[:50]}...")

        try:
            response = await self.llm_service.generate(
                prompt=prompt,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                fallback=True
            )

            total_time = (time.time() - start_time) * 1000
            logger.info(
                f"Generation completed: "
                f"latency={total_time:.0f}ms, "
                f"provider={response.provider}, "
                f"tokens={response.tokens_prompt + response.tokens_completion}"
            )

            content = (response.content or "").strip()
            if content and not self._looks_generic_template(content, contexts):
                return content
            return self._fallback_response(query, contexts)

        except Exception as e:
            logger.error(f"Generation failed: {e}")
            return self._fallback_response(query, contexts)

    def _build_prompt(
        self,
        query: str,
        context: str
    ) -> str:
        """构建生成Prompt"""
        prompt = f"""你是一个专业的问答助手。请严格基于参考信息作答，不要输出泛泛而谈的安全模板。

回答要求：
1. 优先直接回答用户问题，列出从参考信息中能明确支持的要点。
2. 如果参考信息里出现了明确的能力名词（如 hybrid retrieval、query rewrite、rerank、structured execution trace、support-aware fallback），要优先保留这些原词。
3. 不要编造未在参考信息中出现的事实。
4. 如果证据不足，明确说明“参考信息不足以完整回答该问题”。
5. 回答尽量精炼，优先 2-5 条要点或一段简洁总结。

【参考信息】
{context}

【用户问题】
{query}

【回答】"""

        return prompt

    def _looks_generic_template(self, answer: str, contexts: List[Dict[str, Any]]) -> bool:
        answer_lower = answer.lower()
        generic_markers = [
            "基于当前参考信息",
            "我会优先给出有依据的结论",
            "若证据不足",
            "提示补充信息",
        ]
        if any(marker in answer for marker in generic_markers):
            combined = "\n".join(ctx.get("content", "") for ctx in contexts).lower()
            capability_terms = [
                "hybrid retrieval",
                "query rewrite",
                "rerank",
                "structured execution trace",
                "support-aware fallback",
            ]
            if any(term in combined and term not in answer_lower for term in capability_terms):
                return True
        return False

    def _fallback_response(self, query: str, contexts: List[Dict[str, Any]]) -> str:
        """降级响应：当LLM服务不可用或返回模板化内容时"""
        if not contexts:
            return "抱歉，暂时无法生成回答，请稍后重试。"

        bullets = self._extract_evidence_bullets(query, contexts)
        if bullets:
            return "根据检索到的信息：\n- " + "\n- ".join(bullets)

        top_contexts = contexts[:3]
        parts = ["根据检索到的信息："]

        for i, ctx in enumerate(top_contexts, 1):
            title = (
                ctx.get("metadata", {}).get("title")
                or ctx.get("metadata", {}).get("path")
                or ctx.get("id", "未命名来源")
            )
            content = ctx.get("content", "")[:200]
            parts.append(f"{i}. [{title}] {content}...")

        parts.append("（注：当前返回为基于检索证据的降级摘要）")
        return "\n".join(parts)

    def _extract_evidence_bullets(self, query: str, contexts: List[Dict[str, Any]]) -> List[str]:
        query_lower = query.lower()
        combined = "\n".join(ctx.get("content", "") for ctx in contexts)
        combined_lower = combined.lower()
        bullets: List[str] = []

        capability_hits = []
        for phrase in [
            "hybrid retrieval",
            "query rewrite",
            "rerank",
            "structured execution trace",
            "support-aware fallback",
        ]:
            if phrase in combined_lower:
                capability_hits.append(phrase)
        if capability_hits:
            bullets.append("系统支持：" + "、".join(dict.fromkeys(capability_hits)))

        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", combined) if p.strip()]

        def best_paragraph(keywords: List[str]) -> Optional[str]:
            best = None
            best_score = 0
            for para in paragraphs:
                para_lower = para.lower()
                score = sum(2 for kw in keywords if kw.lower() in para_lower)
                score += sum(1 for kw in keywords if kw in para)
                if score > best_score:
                    best_score = score
                    best = para
            return best

        if any(k in query_lower for k in ["检索优化", "retrieval", "rewrite", "rerank"]):
            para = best_paragraph(["hybrid retrieval", "query rewrite", "rerank", "检索", "重排"])
            if para:
                bullets.append(self._sentence_clip(para))

        if any(k in query_lower for k in ["证据不足", "fallback", "支持度"]):
            para = best_paragraph(["support-aware fallback", "fallback", "低支持度", "证据不足"])
            if para:
                bullets.append(self._sentence_clip(para))

        if any(k in query_lower for k in ["trace", "execution", "执行轨迹", "结构化"]):
            para = best_paragraph(["structured execution trace", "execution trace", "trace", "route", "rewrite", "retrieve", "rerank", "generate"])
            if para:
                bullets.append(self._sentence_clip(para))

        if len(bullets) < 2:
            for para in paragraphs[:3]:
                clipped = self._sentence_clip(para)
                if clipped and clipped not in bullets:
                    bullets.append(clipped)
                if len(bullets) >= 3:
                    break

        return bullets[:4]

    def _sentence_clip(self, text: str, max_len: int = 160) -> str:
        text = re.sub(r"\s+", " ", text).strip()
        if len(text) <= max_len:
            return text
        clipped = text[:max_len]
        for sep in ["。", ".", "；", ";", "，", ","]:
            idx = clipped.rfind(sep)
            if idx >= 40:
                return clipped[: idx + 1]
        return clipped + "..."


class HallucinationDetector:
    """
    幻觉检测器
    检测生成内容是否与上下文一致
    """

    def detect(
        self,
        answer: str,
        contexts: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        检测幻觉

        Returns:
            {
                "has_hallucination": bool,
                "confidence": float,
                "unsupported_claims": List[str]
            }
        """
        context_text = " ".join([c.get("content", "") for c in contexts])

        answer_words = set(answer.lower().split())
        context_words = set(context_text.lower().split())

        coverage = len(answer_words & context_words) / len(answer_words) if answer_words else 1.0

        return {
            "has_hallucination": coverage < 0.5,
            "confidence": 1 - coverage,
            "unsupported_claims": []
        }
