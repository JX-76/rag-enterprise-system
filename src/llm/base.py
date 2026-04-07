"""
大模型抽象基类
统一本地模型和在线API的接口
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


class LLMError(Exception):
    """大模型异常"""
    pass


@dataclass
class LLMResponse:
    """大模型响应"""
    text: str
    model: str
    usage: Dict[str, int]
    metadata: Dict[str, Any]


class LLMBase(ABC):
    """
    大模型基类
    
    子类实现：
    - generate: 文本生成
    - chat: 对话生成
    """
    
    def __init__(
        self,
        model_name: str,
        temperature: float = 0.3,
        max_tokens: int = 2048,
        timeout: int = 60
    ):
        """
        Args:
            model_name: 模型名称
            temperature: 温度（0-1，越低越确定）
            max_tokens: 最大生成长度
            timeout: 超时时间（秒）
        """
        self.model_name = model_name
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
    
    @abstractmethod
    def generate(
        self,
        prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> LLMResponse:
        """
        文本生成
        
        Args:
            prompt: 提示词
            temperature: 覆盖默认温度
            max_tokens: 覆盖默认长度
        
        Returns:
            LLMResponse: 生成结果
        """
        pass
    
    @abstractmethod
    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> LLMResponse:
        """
        对话生成
        
        Args:
            messages: 消息列表 [{"role": "user", "content": "..."}]
            temperature: 覆盖默认温度
            max_tokens: 覆盖默认长度
        
        Returns:
            LLMResponse: 生成结果
        """
        pass
    
    def health_check(self) -> bool:
        """健康检查"""
        try:
            response = self.generate("Hello", max_tokens=10)
            return len(response.text) > 0
        except:
            return False
