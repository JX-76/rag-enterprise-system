"""
LLMLingua Compressor - 微软上下文压缩技术
替换原有的简单截断压缩
"""
from typing import List, Dict, Any, Optional
import asyncio
from transformers import AutoTokenizer

from src.core.logging import get_logger

logger = get_logger(__name__)


class LLMLinguaCompressor:
    """
    基于信息熵的上下文压缩
    保留关键信息，去除冗余内容
    """
    
    def __init__(
        self,
        model_name: str = "NousResearch/Llama-2-7b-hf",
        target_token: int = 2000,
        device: str = "cuda"
    ):
        self.model_name = model_name
        self.target_token = target_token
        self.device = device
        
        self.tokenizer = None
        self.compressor = None
        self._initialized = False
    
    async def initialize(self):
        """初始化LLMLingua"""
        if self._initialized:
            return
        
        try:
            from llmlingua import PromptCompressor
            
            logger.info(f"Loading LLMLingua: {self.model_name}")
            
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            self.compressor = PromptCompressor(
                model_name=self.model_name,
                device_map=self.device
            )
            
            self._initialized = True
            logger.info("LLMLingua initialized successfully")
            
        except ImportError:
            logger.warning("llmlingua not installed, using fallback compression")
            self.compressor = None
    
    async def compress(
        self,
        context: str,
        query: str,
        rate: float = 0.5,
        force_tokens: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        压缩上下文
        
        Args:
            context: 原始上下文
            query: 用户查询（用于相关性判断）
            rate: 压缩率（0.5表示压缩50%）
            force_tokens: 强制保留的token
            
        Returns:
            {
                "compressed": str,
                "original_tokens": int,
                "compressed_tokens": int,
                "compression_ratio": float,
                "reduced_tokens": List[str]  # 被压缩掉的内容
            }
        """
        await self.initialize()
        
        if self.compressor is None:
            # Fallback: 简单截断
            return self._fallback_compress(context)
        
        try:
            # 使用LLMLingua压缩
            compressed = self.compressor.compress_prompt(
                context=context,
                instruction="",
                question=query,
                target_token=self.target_token,
                rate=rate,
                condition_compare=True,
                condition_in_question=["after", "before"],
                rank_method="longllmlingua",
                use_sentence_level_filter=False,
                context_budget="*2",
                dynamic_context_compression_ratio=0.3,
                reorder_context="sort"
            )
            
            original_tokens = len(self.tokenizer.encode(context))
            compressed_tokens = len(self.tokenizer.encode(compressed["compressed_prompt"]))
            
            return {
                "compressed": compressed["compressed_prompt"],
                "original_tokens": original_tokens,
                "compressed_tokens": compressed_tokens,
                "compression_ratio": compressed_tokens / original_tokens,
                "saving": compressed.get("saving", 0),
                "method": "llmlingua"
            }
            
        except Exception as e:
            logger.error(f"LLMLingua compression failed: {e}")
            return self._fallback_compress(context)
    
    def _fallback_compress(self, context: str) -> Dict[str, Any]:
        """降级压缩：简单截断"""
        words = context.split()
        if len(words) > self.target_token:
            compressed = " ".join(words[:self.target_token]) + "..."
        else:
            compressed = context
        
        return {
            "compressed": compressed,
            "original_tokens": len(words),
            "compressed_tokens": len(compressed.split()),
            "compression_ratio": len(compressed.split()) / len(words) if words else 1.0,
            "method": "fallback_truncate"
        }


class ContextCompressor:
    """
    上下文压缩管理器
    支持多种压缩策略
    """
    
    def __init__(self):
        self.llmlingua = LLMLinguaCompressor()
        self.compression_stats = []
    
    async def compress_documents(
        self,
        documents: List[Dict[str, Any]],
        query: str,
        max_tokens: int = 2000,
        strategy: str = "llmlingua"
    ) -> List[Dict[str, Any]]:
        """
        压缩文档列表
        
        Args:
            documents: [{"id": str, "content": str, ...}]
            query: 查询
            max_tokens: 最大token数
            strategy: 压缩策略
        """
        if strategy == "llmlingua":
            return await self._compress_with_llmlingua(documents, query, max_tokens)
        else:
            return await self._compress_with_truncate(documents, max_tokens)
    
    async def _compress_with_llmlingua(
        self,
        documents: List[Dict[str, Any]],
        query: str,
        max_tokens: int
    ) -> List[Dict[str, Any]]:
        """使用LLMLingua压缩"""
        compressed_docs = []
        total_tokens = 0
        
        for doc in documents:
            if total_tokens >= max_tokens:
                break
            
            result = await self.llmlingua.compress(
                context=doc["content"],
                query=query,
                rate=0.5
            )
            
            self.compression_stats.append({
                "doc_id": doc["id"],
                "original": result["original_tokens"],
                "compressed": result["compressed_tokens"],
                "ratio": result["compression_ratio"]
            })
            
            compressed_doc = doc.copy()
            compressed_doc["content"] = result["compressed"]
            compressed_doc["compression_info"] = result
            compressed_docs.append(compressed_doc)
            
            total_tokens += result["compressed_tokens"]
        
        return compressed_docs
    
    async def _compress_with_truncate(
        self,
        documents: List[Dict[str, Any]],
        max_tokens: int
    ) -> List[Dict[str, Any]]:
        """简单截断压缩"""
        compressed = []
        total = 0
        
        for doc in documents:
            words = doc["content"].split()
            if total + len(words) > max_tokens:
                remaining = max_tokens - total
                if remaining > 50:
                    truncated = " ".join(words[:remaining])
                    compressed.append({**doc, "content": truncated + "..."})
                break
            compressed.append(doc)
            total += len(words)
        
        return compressed
    
    def get_compression_report(self) -> Dict[str, Any]:
        """生成压缩统计报告"""
        if not self.compression_stats:
            return {"message": "No compression performed"}
        
        ratios = [s["ratio"] for s in self.compression_stats]
        return {
            "total_documents": len(self.compression_stats),
            "avg_compression_ratio": sum(ratios) / len(ratios),
            "min_ratio": min(ratios),
            "max_ratio": max(ratios),
            "total_tokens_before": sum(s["original"] for s in self.compression_stats),
            "total_tokens_after": sum(s["compressed"] for s in self.compression_stats),
        }
