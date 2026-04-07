"""大模型接入模块 - 本地模型 + 在线API"""
from .base import LLMBase, LLMError, LLMResponse
from .local_model import LocalLLM
from .api_model import APILLM

__all__ = ['LLMBase', 'LLMError', 'LLMResponse', 'LocalLLM', 'APILLM']
