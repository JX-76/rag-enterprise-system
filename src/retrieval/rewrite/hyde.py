"""
HyDE (Hypothetical Document Embeddings) Query Rewriter
假设文档嵌入查询改写

核心思想：
- 用户查询通常较短，直接检索效果不佳
- 让LLM生成一段假设的文档（包含答案）
- 用假设文档去检索，而非原始查询
- 利用文档-文档相似度通常高于查询-文档相似度的特点

参考论文: "Precise Zero-Shot Dense Retrieval without Relevance Labels"
"""
from typing import List
import asyncio

from src.core.logging import get_logger

logger = get_logger(__name__)


class HyDERewriter:
    """
    HyDE查询改写器
    
    使用场景：
    - 用户查询简短模糊
    - 需要高召回率的场景
    - 有充足LLM预算的场景
    
    优点：
    - 显著提升检索召回率
    - 零样本，无需训练
    
    缺点：
    - 需要额外LLM调用，增加延迟和成本
    - 假设文档可能与实际文档有偏差
    """
    
    def __init__(self, llm_client=None, prompt_template: str = None):
        """
        初始化HyDE改写器
        
        Args:
            llm_client: LLM客户端，用于生成假设文档
            prompt_template: 自定义prompt模板
        """
        self.llm = llm_client
        self.prompt_template = prompt_template or self._default_prompt()
        
        logger.info("HyDERewriter initialized")
    
    def _default_prompt(self) -> str:
        """默认prompt模板"""
        return """基于用户问题，生成一段可能包含答案的假设文档。

用户问题：{query}

要求：
1. 假设文档应包含可能的答案内容
2. 即使没有确定答案，也根据问题推测最可能的信息
3. 文档应自然流畅，像真实文档一样
4. 文档长度控制在100-200字
5. 不要出现"根据问题"、"假设"等提示词，直接写文档内容

假设文档："""
    
    async def rewrite(self, query: str) -> List[str]:
        """
        改写查询
        
        Args:
            query: 原始查询
            
        Returns:
            改写后的查询列表 [原始查询, 假设文档]
        """
        logger.debug(f"HyDE rewriting: '{query[:50]}...'")
        
        # 生成假设文档
        hypothetical_doc = await self._generate_hypothetical_doc(query)
        
        if hypothetical_doc:
            logger.debug(f"Generated hypothetical doc: '{hypothetical_doc[:100]}...'")
            return [query, hypothetical_doc]
        else:
            # 生成失败，返回原查询
            return [query]
    
    async def _generate_hypothetical_doc(self, query: str) -> str:
        """生成假设文档"""
        if not self.llm:
            # Mock实现
            await asyncio.sleep(0.01)
            return f"关于'{query[:30]}'的相关信息：这是一个重要话题，涉及多个方面..."
        
        try:
            prompt = self.prompt_template.format(query=query)
            
            response = await self.llm.generate(
                prompt,
                temperature=0.7,
                max_tokens=200,
                stop_sequences=["\n\n"]
            )
            
            # 清理响应
            doc = response.strip()
            
            # 移除可能的引号
            if doc.startswith('"') and doc.endswith('"'):
                doc = doc[1:-1]
            
            return doc
            
        except Exception as e:
            logger.error(f"Failed to generate hypothetical doc: {e}")
            return ""
    
    async def rewrite_batch(self, queries: List[str]) -> List[List[str]]:
        """批量改写"""
        tasks = [self.rewrite(q) for q in queries]
        return await asyncio.gather(*tasks)


class HyDEWithExpansion(HyDERewriter):
    """
    HyDE + 扩展变体
    
    生成多个不同角度的假设文档，进一步提升召回
    """
    
    def __init__(self, llm_client=None, num_variants: int = 3):
        super().__init__(llm_client)
        self.num_variants = num_variants
    
    async def rewrite(self, query: str) -> List[str]:
        """生成多个假设文档变体"""
        results = [query]  # 保留原查询
        
        # 生成多个变体
        for i in range(self.num_variants):
            variant_prompt = self._variant_prompt(i)
            doc = await self._generate_with_prompt(query, variant_prompt)
            if doc:
                results.append(doc)
        
        return results
    
    def _variant_prompt(self, variant_idx: int) -> str:
        """不同角度的prompt"""
        prompts = [
            "从定义和概念角度解释：",
            "通过具体例子说明：",
            "分析其重要性和影响："
        ]
        angle = prompts[variant_idx % len(prompts)]
        
        return f"""基于用户问题，{angle}

用户问题：{{query}}

生成一段包含相关信息的文档（100-150字）："""
    
    async def _generate_with_prompt(self, query: str, prompt_template: str) -> str:
        """使用指定prompt生成"""
        if not self.llm:
            return f"变体回答：关于'{query[:20]}'的信息..."
        
        prompt = prompt_template.format(query=query)
        
        try:
            response = await self.llm.generate(
                prompt,
                temperature=0.8,
                max_tokens=150
            )
            return response.strip()
        except Exception as e:
            logger.error(f"Generation failed: {e}")
            return ""
