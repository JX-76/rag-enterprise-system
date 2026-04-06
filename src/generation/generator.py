"""
LLM Generator - LLM生成器
支持上下文压缩、引用生成、幻觉检测
"""
from typing import List, Dict, Any, Optional
import time
import re

from src.core.config import settings
from src.core.logging import get_logger
from src.services.llm_service import get_llm_service, LLMResponse

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
            content = ctx.get("content", "")
            
            # 简化压缩：直接截断
            # 实际应使用LLMLingua等工具
            if total_length + len(content) > max_tokens * 4:  # 粗略估算
                remaining = max_tokens * 4 - total_length
                if remaining > 200:
                    content = content[:remaining] + "..."
                else:
                    break
            
            compressed_parts.append(content)
            total_length += len(content)
        
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
        self.temperature = 0.7
    
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
        
        # 压缩上下文
        context_text = self.context_compressor.compress(
            contexts,
            max_tokens=self.max_context_length
        )
        
        # 构建Prompt
        prompt = self._build_prompt(query, context_text)
        
        logger.debug(f"Generating answer for query: {query[:50]}...")
        
        try:
            # 调用LLM服务
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
            
            return response.content
            
        except Exception as e:
            logger.error(f"Generation failed: {e}")
            # 降级：返回检索结果摘要
            return self._fallback_response(contexts)
    
    def _build_prompt(
        self,
        query: str,
        context: str
    ) -> str:
        """构建生成Prompt"""
        prompt = f"""你是一个专业的问答助手。请基于以下参考信息回答用户的问题。

【参考信息】
{context}

【用户问题】
{query}

请根据参考信息回答问题。如果参考信息不足以回答问题，请明确说明无法回答。

【回答】"""
        
        return prompt
    
    def _fallback_response(self, contexts: List[Dict[str, Any]]) -> str:
        """降级响应：当LLM服务不可用时"""
        if not contexts:
            return "抱歉，暂时无法生成回答，请稍后重试。"
        
        # 返回Top3检索结果作为回答
        top_contexts = contexts[:3]
        parts = ["根据检索到的信息："]
        
        for i, ctx in enumerate(top_contexts, 1):
            content = ctx.get("content", "")[:200]
            parts.append(f"{i}. {content}...")
        
        parts.append("\n（注：当前LLM服务暂时不可用，以上为检索到的原始信息）")
        
        return "\n".join(parts)


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
        # 简化实现
        # 实际应使用NLI模型检测
        
        context_text = " ".join([c.get("content", "") for c in contexts])
        
        # 检查回答中的关键词是否在上下文中
        answer_words = set(answer.lower().split())
        context_words = set(context_text.lower().split())
        
        # 计算覆盖率
        coverage = len(answer_words & context_words) / len(answer_words) if answer_words else 1.0
        
        return {
            "has_hallucination": coverage < 0.5,
            "confidence": 1 - coverage,
            "unsupported_claims": []
        }
