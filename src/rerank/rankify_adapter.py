"""
Rankify Adapter - 接入24个重排模型
替换原有的mock实现
"""
from typing import List, Dict, Any
import asyncio
from rankify import Reranker  # pip install rankify

from src.core.logging import get_logger

logger = get_logger(__name__)


class RankifyAdapter:
    """
    适配器模式：将Rankify接入现有三阶段重排序框架
    """
    
    SUPPORTED_MODELS = {
        # 轻量级 - Stage 1
        "minilm": "cross-encoder/ms-marco-MiniLM-L-6-v2",
        "electra": "cross-encoder/ms-marco-electra-base",
        
        # 重量级 - Stage 2  
        "bge-reranker": "BAAI/bge-reranker-large",
        "cohere": "cohere-rerank",
        "jina": "jina-reranker-v1-base-en",
        
        # 长文档专用
        "longllmlingua": "LongLLMLingua",
        "lost-in-the-middle": "LostInTheMiddle",
    }
    
    def __init__(self, model_name: str = "bge-reranker"):
        self.model_name = model_name
        self.reranker = None
        self._initialized = False
    
    async def initialize(self):
        """异步初始化模型"""
        if self._initialized:
            return
        
        logger.info(f"Initializing Rankify model: {self.model_name}")
        
        # 在线API模型
        if self.model_name in ["cohere", "jina"]:
            self.reranker = Reranker(
                self.SUPPORTED_MODELS[self.model_name],
                api_key=self._get_api_key()
            )
        else:
            # 本地模型
            self.reranker = Reranker(self.SUPPORTED_MODELS[self.model_name])
        
        self._initialized = True
        logger.info(f"Rankify model {self.model_name} loaded")
    
    async def rerank(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """
        执行重排序
        
        Args:
            query: 查询
            documents: [{"id": str, "content": str, "metadata": {}}]
            top_k: 返回top-k
        """
        await self.initialize()
        
        # 提取文本
        doc_texts = [doc["content"] for doc in documents]
        doc_ids = [doc["id"] for doc in documents]
        
        # 执行重排序
        try:
            results = self.reranker.rerank(
                query=query,
                documents=doc_texts,
                top_k=top_k
            )
            
            # 构建返回格式
            reranked = []
            for result in results:
                idx = result["index"]
                reranked.append({
                    "id": doc_ids[idx],
                    "content": documents[idx]["content"],
                    "score": result["score"],
                    "metadata": documents[idx].get("metadata", {}),
                    "rank": result["rank"]
                })
            
            return reranked
            
        except Exception as e:
            logger.error(f"Rankify reranking failed: {e}")
            # 降级：返回原始排序
            return documents[:top_k]
    
    def _get_api_key(self) -> str:
        """获取API Key"""
        from src.core.config import settings
        if self.model_name == "cohere":
            return settings.COHERE_API_KEY
        elif self.model_name == "jina":
            return settings.JINA_API_KEY
        return ""


class HybridReranker:
    """
    混合重排序：Stage1(轻量) + Stage2(重量) + Stage3(优化)
    使用真实模型替换mock
    """
    
    def __init__(self):
        self.stage1 = RankifyAdapter("minilm")      # 轻量快速筛选
        self.stage2 = RankifyAdapter("bge-reranker") # 重量精排
        self.stage3 = RankifyAdapter("longllmlingua") # 长文档优化
    
    async def rerank_pipeline(
        self,
        query: str,
        candidates: List[Dict[str, Any]],
        final_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        三阶段重排序管道
        
        Stage 1: MiniLM快速筛选 Top 100 → Top 30
        Stage 2: BGE-Reranker精排 Top 30 → Top 10
        Stage 3: LongLLMLingua长文档优化 Top 10 → Top 5
        """
        logger.info(f"Starting 3-stage reranking for '{query[:50]}...'")
        
        # Stage 1: 轻量筛选
        stage1_results = await self.stage1.rerank(query, candidates, top_k=30)
        logger.debug(f"Stage 1: {len(candidates)} → {len(stage1_results)}")
        
        # Stage 2: 精排
        stage2_results = await self.stage2.rerank(query, stage1_results, top_k=10)
        logger.debug(f"Stage 2: {len(stage1_results)} → {len(stage2_results)}")
        
        # Stage 3: 长文档优化
        stage3_results = await self.stage3.rerank(query, stage2_results, top_k=final_k)
        logger.debug(f"Stage 3: {len(stage2_results)} → {len(stage3_results)}")
        
        return stage3_results


# 便捷函数
async def rerank_with_best_model(
    query: str,
    documents: List[Dict[str, Any]],
    model: str = "bge-reranker"
) -> List[Dict[str, Any]]:
    """使用指定模型重排序"""
    adapter = RankifyAdapter(model)
    return await adapter.rerank(query, documents)
