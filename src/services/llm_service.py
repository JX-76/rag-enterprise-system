"""
LLM Service - LLM推理服务
支持OpenAI/Anthropic，流式输出，重试，降级
"""
import asyncio
from typing import AsyncGenerator, Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum
import time

import openai
import anthropic
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from src.core.config import settings
from src.core.logging import get_logger
from src.core.monitoring import metrics

logger = get_logger(__name__)


class LLMProvider(Enum):
    """LLM提供商"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


@dataclass
class LLMResponse:
    """LLM响应"""
    content: str
    provider: str
    model: str
    tokens_prompt: int
    tokens_completion: int
    latency_ms: float
    finish_reason: Optional[str] = None


class OpenAIClient:
    """OpenAI客户端封装"""
    
    def __init__(self):
        self.client = openai.AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            timeout=60.0
        )
        self.model = settings.LLM_MODEL
    
    @retry(
        retry=retry_if_exception_type((
            openai.RateLimitError,
            openai.APITimeoutError,
            openai.APIConnectionError
        )),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    async def generate(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        stream: bool = False
    ) -> LLMResponse:
        """生成文本"""
        start_time = time.time()
        
        try:
            if stream:
                return await self._generate_stream(prompt, temperature, max_tokens)
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一个有帮助的助手。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            latency = (time.time() - start_time) * 1000
            
            return LLMResponse(
                content=response.choices[0].message.content,
                provider="openai",
                model=self.model,
                tokens_prompt=response.usage.prompt_tokens,
                tokens_completion=response.usage.completion_tokens,
                latency_ms=latency,
                finish_reason=response.choices[0].finish_reason
            )
            
        except Exception as e:
            logger.error(f"OpenAI generation failed: {e}")
            raise
    
    async def _generate_stream(
        self,
        prompt: str,
        temperature: float,
        max_tokens: int
    ) -> LLMResponse:
        """流式生成"""
        start_time = time.time()
        content_parts = []
        
        stream = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "你是一个有帮助的助手。"},
                {"role": "user", "content": prompt}
            ],
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True
        )
        
        async for chunk in stream:
            if chunk.choices[0].delta.content:
                content_parts.append(chunk.choices[0].delta.content)
        
        latency = (time.time() - start_time) * 1000
        
        return LLMResponse(
            content="".join(content_parts),
            provider="openai",
            model=self.model,
            tokens_prompt=0,  # 流式不返回token数
            tokens_completion=0,
            latency_ms=latency
        )


class AnthropicClient:
    """Anthropic客户端封装"""
    
    def __init__(self):
        self.client = anthropic.AsyncAnthropic(
            api_key=settings.ANTHROPIC_API_KEY
        )
        self.model = "claude-3-sonnet-20240229"
    
    @retry(
        retry=retry_if_exception_type((
            anthropic.RateLimitError,
            anthropic.APITimeoutError
        )),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    async def generate(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        stream: bool = False
    ) -> LLMResponse:
        """生成文本"""
        start_time = time.time()
        
        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=[{"role": "user", "content": prompt}]
            )
            
            latency = (time.time() - start_time) * 1000
            
            return LLMResponse(
                content=response.content[0].text,
                provider="anthropic",
                model=self.model,
                tokens_prompt=response.usage.input_tokens,
                tokens_completion=response.usage.output_tokens,
                latency_ms=latency
            )
            
        except Exception as e:
            logger.error(f"Anthropic generation failed: {e}")
            raise


class LLMService:
    """
    LLM服务
    
    特性：
    - 多提供商支持（OpenAI/Anthropic）
    - 自动降级（主失败切换到备用）
    - 流式输出
    - Token消耗统计
    """
    
    def __init__(self):
        self.clients: Dict[str, Any] = {}
        self.primary_provider = LLMProvider.OPENAI
        
        # 初始化客户端
        if settings.OPENAI_API_KEY:
            self.clients[LLMProvider.OPENAI.value] = OpenAIClient()
            logger.info("OpenAI client initialized")
        
        if settings.ANTHROPIC_API_KEY:
            self.clients[LLMProvider.ANTHROPIC.value] = AnthropicClient()
            logger.info("Anthropic client initialized")
        
        if not self.clients:
            logger.warning("No LLM clients configured. Using mock mode.")
    
    async def generate(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        stream: bool = False,
        fallback: bool = True
    ) -> LLMResponse:
        """
        生成文本
        
        Args:
            prompt: 输入提示
            temperature: 温度
            max_tokens: 最大token数
            stream: 是否流式
            fallback: 失败时是否降级
        """
        providers = list(self.clients.keys())
        
        if not providers:
            # Mock模式
            return LLMResponse(
                content="[MOCK] " + prompt[:100] + "...",
                provider="mock",
                model="mock",
                tokens_prompt=0,
                tokens_completion=0,
                latency_ms=0
            )
        
        # 优先使用主提供商
        provider_order = [self.primary_provider.value] + [
            p for p in providers if p != self.primary_provider.value
        ]
        
        last_error = None
        
        for provider in provider_order:
            client = self.clients.get(provider)
            if not client:
                continue
            
            try:
                logger.debug(f"Trying LLM provider: {provider}")
                response = await client.generate(
                    prompt, temperature, max_tokens, stream
                )
                
                # 记录指标
                metrics.generation_latency.observe(response.latency_ms / 1000)
                
                logger.info(
                    f"LLM generation completed: "
                    f"provider={provider}, "
                    f"latency={response.latency_ms:.0f}ms, "
                    f"tokens={response.tokens_prompt + response.tokens_completion}"
                )
                
                return response
                
            except Exception as e:
                last_error = e
                logger.warning(f"Provider {provider} failed: {e}")
                
                if not fallback:
                    break
        
        # 全部失败
        logger.error(f"All LLM providers failed: {last_error}")
        raise last_error
    
    async def generate_stream(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> AsyncGenerator[str, None]:
        """流式生成"""
        # 简化实现：直接生成后分段yield
        response = await self.generate(
            prompt, temperature, max_tokens, stream=False
        )
        
        # 模拟流式输出
        words = response.content.split()
        for word in words:
            yield word + " "
            await asyncio.sleep(0.01)


# 全局实例
_llm_service: Optional[LLMService] = None


def get_llm_service() -> LLMService:
    """获取全局LLM服务"""
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service
