"""
LLM Service - 大语言模型服务

支持:
- 本地模型 (Qwen, ChatGLM等 via transformers)
- API模型 (OpenAI, 通义千问API等)
- 引用溯源
- 幻觉检测
"""
import re
import os
from typing import List, Dict, Any, Optional, Generator
from dataclasses import dataclass
from abc import ABC, abstractmethod
import logging

logger = logging.getLogger(__name__)

# 尝试导入transformers
try:
    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM, TextIteratorStreamer
    from threading import Thread
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    torch = None
    AutoTokenizer = None
    AutoModelForCausalLM = None
    TextIteratorStreamer = None

# 尝试导入openai
try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    openai = None


@dataclass
class LLMResponse:
    """LLM响应"""
    content: str
    citations: List[Dict[str, Any]]  # 引用信息
    hallucination_detected: bool = False
    hallucination_details: List[str] = None
    metadata: Dict[str, Any] = None


@dataclass
class Citation:
    """引用信息"""
    text: str  # 引用的原文
    source: str  # 来源文档
    chunk_id: str
    relevance_score: float
    start_pos: int = 0
    end_pos: int = 0


class BaseLLM(ABC):
    """LLM基类"""
    
    @abstractmethod
    def generate(
        self,
        prompt: str,
        max_tokens: int = 512,
        temperature: float = 0.7
    ) -> str:
        """生成文本"""
        pass
    
    @abstractmethod
    def generate_stream(
        self,
        prompt: str,
        max_tokens: int = 512,
        temperature: float = 0.7
    ) -> Generator[str, None, None]:
        """流式生成"""
        pass


class LocalLLM(BaseLLM):
    """
    本地LLM (transformers)
    
    使用示例:
        llm = LocalLLM("Qwen/Qwen2-1.5B-Instruct")
        response = llm.generate("你好")
    """
    
    def __init__(
        self,
        model_name: str = "Qwen/Qwen2-1.5B-Instruct",
        device: str = "auto",
        load_in_8bit: bool = False
    ):
        if not TRANSFORMERS_AVAILABLE:
            raise ImportError("transformers required. Install: pip install transformers torch")
        
        self.model_name = model_name
        self.device = device if device != "auto" else ("cuda" if torch.cuda.is_available() else "cpu")
        self.load_in_8bit = load_in_8bit
        
        self._tokenizer = None
        self._model = None
        self._loaded = False
    
    def _load_model(self):
        """加载模型"""
        if self._loaded:
            return
        
        logger.info(f"Loading model: {self.model_name}")
        
        self._tokenizer = AutoTokenizer.from_pretrained(
            self.model_name,
            trust_remote_code=True
        )
        
        load_kwargs = {
            "trust_remote_code": True,
            "torch_dtype": torch.float16 if self.device == "cuda" else torch.float32,
        }
        
        if self.load_in_8bit and self.device == "cuda":
            load_kwargs["load_in_8bit"] = True
        else:
            load_kwargs["device_map"] = "auto" if self.device == "cuda" else None
        
        self._model = AutoModelForCausalLM.from_pretrained(
            self.model_name,
            **load_kwargs
        )
        
        if not self.load_in_8bit and self.device == "cpu":
            self._model = self._model.to(self.device)
        
        self._loaded = True
        logger.info(f"Model loaded on {self.device}")
    
    def _build_prompt(self, messages: List[Dict[str, str]]) -> str:
        """构建对话prompt"""
        if "Qwen" in self.model_name:
            # Qwen chat template
            return self._tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True
            )
        else:
            # 通用模板
            prompt = ""
            for msg in messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if role == "system":
                    prompt += f"System: {content}\n"
                elif role == "user":
                    prompt += f"User: {content}\n"
                elif role == "assistant":
                    prompt += f"Assistant: {content}\n"
            prompt += "Assistant: "
            return prompt
    
    def generate(
        self,
        prompt: str,
        max_tokens: int = 512,
        temperature: float = 0.7
    ) -> str:
        """生成文本"""
        self._load_model()
        
        messages = [{"role": "user", "content": prompt}]
        formatted_prompt = self._build_prompt(messages)
        
        inputs = self._tokenizer(
            formatted_prompt,
            return_tensors="pt"
        ).to(self.device)
        
        with torch.no_grad():
            outputs = self._model.generate(
                **inputs,
                max_new_tokens=max_tokens,
                temperature=temperature,
                do_sample=temperature > 0,
                top_p=0.9,
                pad_token_id=self._tokenizer.eos_token_id
            )
        
        response = self._tokenizer.decode(
            outputs[0][inputs.input_ids.shape[1]:],
            skip_special_tokens=True
        )
        
        return response.strip()
    
    def generate_stream(
        self,
        prompt: str,
        max_tokens: int = 512,
        temperature: float = 0.7
    ) -> Generator[str, None, None]:
        """流式生成"""
        self._load_model()
        
        messages = [{"role": "user", "content": prompt}]
        formatted_prompt = self._build_prompt(messages)
        
        inputs = self._tokenizer(
            formatted_prompt,
            return_tensors="pt"
        ).to(self.device)
        
        streamer = TextIteratorStreamer(
            self._tokenizer,
            skip_special_tokens=True
        )
        
        generation_kwargs = dict(
            **inputs,
            max_new_tokens=max_tokens,
            temperature=temperature,
            do_sample=temperature > 0,
            top_p=0.9,
            pad_token_id=self._tokenizer.eos_token_id,
            streamer=streamer
        )
        
        thread = Thread(target=self._model.generate, kwargs=generation_kwargs)
        thread.start()
        
        generated_text = ""
        for text in streamer:
            generated_text += text
            yield text


class APILLM(BaseLLM):
    """
    API LLM (OpenAI格式)
    
    使用示例:
        llm = APILLM(api_key="sk-...", base_url="https://api.openai.com/v1")
        response = llm.generate("你好")
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: str = "gpt-3.5-turbo"
    ):
        if not OPENAI_AVAILABLE:
            raise ImportError("openai required. Install: pip install openai")
        
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.base_url = base_url or os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        self.model = model
        
        self._client = openai.OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )
    
    def generate(
        self,
        prompt: str,
        max_tokens: int = 512,
        temperature: float = 0.7
    ) -> str:
        """生成文本"""
        response = self._client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=temperature
        )
        return response.choices[0].message.content
    
    def generate_stream(
        self,
        prompt: str,
        max_tokens: int = 512,
        temperature: float = 0.7
    ) -> Generator[str, None, None]:
        """流式生成"""
        response = self._client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=temperature,
            stream=True
        )
        
        for chunk in response:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


class RAGGenerator:
    """
    RAG生成器
    
    整合检索和生成，支持引用溯源
    """
    
    def __init__(
        self,
        llm: BaseLLM,
        retriever=None,
        enable_citation: bool = True,
        enable_hallucination_check: bool = True
    ):
        self.llm = llm
        self.retriever = retriever
        self.enable_citation = enable_citation
        self.enable_hallucination_check = enable_hallucination_check
    
    def generate(
        self,
        query: str,
        context_docs: List[Dict[str, Any]] = None,
        retrieve_top_k: int = 5
    ) -> LLMResponse:
        """
        生成回答
        
        Args:
            query: 用户查询
            context_docs: 上下文文档（可选，不提供则自动检索）
            retrieve_top_k: 检索数量
        """
        # 1. 检索（如果需要）
        if context_docs is None and self.retriever:
            # 需要实现检索逻辑
            context_docs = []
        
        context_docs = context_docs or []
        
        # 2. 构建prompt
        prompt = self._build_rag_prompt(query, context_docs)
        
        # 3. 生成
        content = self.llm.generate(prompt)
        
        # 4. 提取引用
        citations = []
        if self.enable_citation and context_docs:
            citations = self._extract_citations(content, context_docs)
        
        # 5. 幻觉检测
        hallucination_detected = False
        hallucination_details = []
        if self.enable_hallucination_check:
            hallucination_detected, hallucination_details = self._check_hallucination(
                content, context_docs
            )
        
        return LLMResponse(
            content=content,
            citations=citations,
            hallucination_detected=hallucination_detected,
            hallucination_details=hallucination_details,
            metadata={
                "query": query,
                "context_count": len(context_docs),
                "prompt_length": len(prompt)
            }
        )
    
    def _build_rag_prompt(
        self,
        query: str,
        context_docs: List[Dict[str, Any]]
    ) -> str:
        """构建RAG prompt"""
        # 构建上下文
        context_text = ""
        for i, doc in enumerate(context_docs, 1):
            context_text += f"\n[{i}] {doc.get('text', '')}\n"
        
        prompt = f"""基于以下参考资料回答问题。

参考资料:
{context_text}

问题: {query}

请根据参考资料回答，并在回答中标注引用来源（如[1]、[2]）。如果参考资料中没有相关信息，请明确说明"根据提供的资料无法回答"。

回答:"""
        
        return prompt
    
    def _extract_citations(
        self,
        content: str,
        context_docs: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """提取引用"""
        citations = []
        
        # 查找 [数字] 格式的引用
        citation_pattern = r'\[(\d+)\]'
        matches = re.finditer(citation_pattern, content)
        
        for match in matches:
            idx = int(match.group(1)) - 1
            if 0 <= idx < len(context_docs):
                doc = context_docs[idx]
                citations.append({
                    "index": idx + 1,
                    "text": doc.get('text', '')[:200] + "...",
                    "source": doc.get('metadata', {}).get('source', 'unknown'),
                    "chunk_id": doc.get('id', 'unknown')
                })
        
        return citations
    
    def _check_hallucination(
        self,
        content: str,
        context_docs: List[Dict[str, Any]]
    ) -> tuple[bool, List[str]]:
        """
        幻觉检测
        
        简单实现：检查关键信息是否在上下文中有支持
        """
        hallucination_details = []
        
        # 合并所有上下文
        all_context = " ".join([d.get('text', '') for d in context_docs]).lower()
        
        # 提取回答中的关键短语（简单规则：提取引号内容、数字、专有名词）
        # 这里使用简化检查
        suspicious_patterns = [
            r'根据我的经验',
            r'我认为',
            r'我觉得',
            r'据我所知',
            r'可能',
            r'也许',
            r'猜测'
        ]
        
        for pattern in suspicious_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                hallucination_details.append(f"发现主观表述: {pattern}")
        
        # 检查是否有明确声明无法回答
        if "无法回答" in content or "无法找到" in content:
            pass  # 这是诚实的
        
        return len(hallucination_details) > 0, hallucination_details


# 便捷函数
def get_llm(
    llm_type: str = "local",
    model_name: str = None,
    api_key: str = None
) -> BaseLLM:
    """
    获取LLM实例
    
    Args:
        llm_type: 'local' 或 'api'
        model_name: 模型名称
        api_key: API密钥（API类型需要）
    """
    if llm_type == "local":
        model = model_name or "Qwen/Qwen2-1.5B-Instruct"
        return LocalLLM(model)
    elif llm_type == "api":
        model = model_name or "gpt-3.5-turbo"
        return APILLM(api_key=api_key, model=model)
    else:
        raise ValueError(f"Unknown LLM type: {llm_type}")
