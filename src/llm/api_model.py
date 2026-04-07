"""
在线大模型API接入
支持通义千问、文心一言、OpenAI等
"""
import os
from typing import List, Dict, Any, Optional
import logging
import httpx

from .base import LLMBase, LLMError, LLMResponse

logger = logging.getLogger(__name__)


class APILLM(LLMBase):
    """
    在线API大模型基类
    """
    
    def __init__(
        self,
        model_name: str,
        api_key: str,
        base_url: str,
        temperature: float = 0.3,
        max_tokens: int = 2048,
        timeout: int = 60
    ):
        super().__init__(model_name, temperature, max_tokens, timeout)
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.client = httpx.Client(timeout=timeout)
    
    def _make_request(self, messages: List[Dict[str, str]], temperature: float, max_tokens: int) -> Dict[str, Any]:
        """发送请求 - 子类实现"""
        raise NotImplementedError
    
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
            return self._parse_response(result)
        except Exception as e:
            logger.error(f"API调用失败: {e}")
            raise LLMError(f"API调用失败: {str(e)}")
    
    def _parse_response(self, result: Dict[str, Any]) -> LLMResponse:
        """解析响应 - 子类实现"""
        raise NotImplementedError
    
    def __del__(self):
        if hasattr(self, 'client'):
            self.client.close()


class DashScopeLLM(APILLM):
    """
    通义千问 (阿里云 DashScope)
    
    使用说明:
    1. 获取API Key: https://dashscope.aliyun.com
    2. 设置环境变量: DASHSCOPE_API_KEY
    
    推荐模型:
    - qwen-turbo: 快速便宜
    - qwen-plus: 平衡性能
    - qwen-max: 最强性能
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "qwen-turbo",
        temperature: float = 0.3,
        max_tokens: int = 2048,
        timeout: int = 60
    ):
        api_key = api_key or os.getenv("DASHSCOPE_API_KEY")
        if not api_key:
            raise LLMError("DASHSCOPE_API_KEY 未设置")
        
        super().__init__(
            model_name=model,
            api_key=api_key,
            base_url="https://dashscope.aliyuncs.com/api/v1",
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout
        )
    
    def _make_request(self, messages: List[Dict[str, str]], temperature: float, max_tokens: int) -> Dict[str, Any]:
        """发送请求"""
        url = f"{self.base_url}/services/aigc/text-generation/generation"
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        data = {
            "model": self.model_name,
            "input": {
                "messages": messages
            },
            "parameters": {
                "temperature": temperature,
                "max_tokens": max_tokens,
                "result_format": "message"
            }
        }
        
        try:
            response = self.client.post(url, json=data, headers=headers)
            response.raise_for_status()
            return response.json()
        except httpx.TimeoutException:
            raise LLMError(f"请求超时（{self.timeout}秒）")
        except Exception as e:
            raise LLMError(f"请求失败: {str(e)}")
    
    def _parse_response(self, result: Dict[str, Any]) -> LLMResponse:
        """解析响应"""
        output = result.get("output", {})
        usage = result.get("usage", {})
        
        message = output.get("choices", [{}])[0].get("message", {})
        content = message.get("content", "")
        
        return LLMResponse(
            text=content,
            model=self.model_name,
            usage={
                "prompt_tokens": usage.get("input_tokens", 0),
                "completion_tokens": usage.get("output_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0)
            },
            metadata={"finish_reason": output.get("choices", [{}])[0].get("finish_reason")}
        )


class OpenAILLM(APILLM):
    """
    OpenAI / OpenAI兼容接口
    
    支持:
    - OpenAI官方
    - Azure OpenAI
    - 其他兼容OpenAI格式的服务
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-3.5-turbo",
        base_url: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 2048,
        timeout: int = 60
    ):
        api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise LLMError("OPENAI_API_KEY 未设置")
        
        base_url = base_url or os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        
        super().__init__(
            model_name=model,
            api_key=api_key,
            base_url=base_url,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout
        )
    
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
            "max_tokens": max_tokens
        }
        
        try:
            response = self.client.post(url, json=data, headers=headers)
            response.raise_for_status()
            return response.json()
        except httpx.TimeoutException:
            raise LLMError(f"请求超时（{self.timeout}秒）")
        except Exception as e:
            raise LLMError(f"请求失败: {str(e)}")
    
    def _parse_response(self, result: Dict[str, Any]) -> LLMResponse:
        """解析响应"""
        choice = result.get("choices", [{}])[0]
        message = choice.get("message", {})
        content = message.get("content", "")
        usage = result.get("usage", {})
        
        return LLMResponse(
            text=content,
            model=self.model_name,
            usage=usage,
            metadata={"finish_reason": choice.get("finish_reason")}
        )


# 便捷函数
def create_llm(mode: str = "api", **kwargs) -> APILLM:
    """
    创建LLM实例
    
    Args:
        mode: "api" | "local" | "dashscope" | "openai"
        **kwargs: 其他参数
    
    Returns:
        LLMBase实例
    """
    if mode == "dashscope":
        return DashScopeLLM(**kwargs)
    elif mode == "openai":
        return OpenAILLM(**kwargs)
    elif mode == "local":
        from .local_model import LocalLLM
        return LocalLLM(**kwargs)
    else:
        # 默认使用 DashScope
        return DashScopeLLM(**kwargs)
