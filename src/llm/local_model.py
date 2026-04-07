"""
本地大模型接入
支持 LM Studio、Ollama 等本地部署的模型
使用 4-bit 量化降低显存占用
"""
import os
from typing import List, Dict, Any, Optional
import logging
import httpx

from .base import LLMBase, LLMError, LLMResponse

logger = logging.getLogger(__name__)


class LocalLLM(LLMBase):
    """
    本地大模型实现
    
    兼容 OpenAI API 格式的本地服务（LM Studio、Ollama、vLLM等）
    
    使用建议：
    - 4-bit 量化模型（如 Qwen-7B-Chat-Int4）
    - 显存 4GB 以上即可运行
    - 上下文长度建议 2048
    """
    
    def __init__(
        self,
        model_name: str = "local-model",
        base_url: str = "http://localhost:1234/v1",
        api_key: str = "not-needed",
        temperature: float = 0.3,
        max_tokens: int = 2048,
        timeout: int = 60
    ):
        """
        Args:
            model_name: 模型名称（本地服务通常忽略）
            base_url: 本地服务地址（LM Studio 默认: http://localhost:1234/v1）
            api_key: API Key（本地服务通常不需要）
        """
        super().__init__(model_name, temperature, max_tokens, timeout)
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.client = httpx.Client(timeout=timeout)
        
        logger.info(f"本地模型初始化: {base_url}")
    
    def _make_request(self, messages: List[Dict[str, str]], temperature: float, max_tokens: int) -> Dict[str, Any]:
        """发送请求"""
        url = f"{self.base_url}/chat/completions"
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        data = {
            "model": self.model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False
        }
        
        try:
            response = self.client.post(url, json=data, headers=headers)
            response.raise_for_status()
            return response.json()
        except httpx.TimeoutException:
            raise LLMError(f"请求超时（{self.timeout}秒）")
        except httpx.ConnectError:
            raise LLMError(f"无法连接到本地模型服务: {self.base_url}")
        except Exception as e:
            raise LLMError(f"请求失败: {str(e)}")
    
    def generate(
        self,
        prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> LLMResponse:
        """文本生成"""
        messages = [{"role": "user", "content": prompt}]
        return self.chat(messages, temperature, max_tokens)
    
    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> LLMResponse:
        """对话生成"""
        temp = temperature if temperature is not None else self.temperature
        tokens = max_tokens if max_tokens is not None else self.max_tokens
        
        try:
            result = self._make_request(messages, temp, tokens)
            
            choice = result.get("choices", [{}])[0]
            message = choice.get("message", {})
            content = message.get("content", "")
            
            usage = result.get("usage", {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0
            })
            
            return LLMResponse(
                text=content,
                model=self.model_name,
                usage=usage,
                metadata={"finish_reason": choice.get("finish_reason")}
            )
            
        except Exception as e:
            logger.error(f"生成失败: {e}")
            raise LLMError(f"生成失败: {str(e)}")
    
    def __del__(self):
        """清理资源"""
        if hasattr(self, 'client'):
            self.client.close()


class LMStudioLLM(LocalLLM):
    """
    LM Studio 专用接口
    
    使用 LM Studio 启动本地模型服务：
    1. 下载并安装 LM Studio
    2. 下载模型（推荐 Qwen-7B-Chat-GGUF）
    3. 设置参数：
       - Context Length: 2048
       - GPU Offload: Max
       - Quantization: q4_k_m
    4. 启动本地服务器
    5. API 地址: http://localhost:1234/v1
    """
    
    def __init__(
        self,
        temperature: float = 0.3,
        max_tokens: int = 2048,
        timeout: int = 60
    ):
        super().__init__(
            model_name="local-model",
            base_url="http://localhost:1234/v1",
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout
        )


class OllamaLLM(LocalLLM):
    """
    Ollama 专用接口
    
    使用 Ollama：
    1. 安装 Ollama
    2. 拉取模型: ollama pull qwen:7b
    3. 启动服务: ollama serve
    4. API 地址: http://localhost:11434/v1
    """
    
    def __init__(
        self,
        model_name: str = "qwen:7b",
        temperature: float = 0.3,
        max_tokens: int = 2048,
        timeout: int = 60
    ):
        super().__init__(
            model_name=model_name,
            base_url="http://localhost:11434/v1",
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout
        )
