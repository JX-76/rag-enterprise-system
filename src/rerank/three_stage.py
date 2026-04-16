"""
Three-Stage Reranking - 三阶重排序
Stage 1: 轻量级预排序 (BGE-small) - Top100 → Top30
Stage 2: 核心精排 (BGE-Reranker) - Top30 → Top10
Stage 3: 生成适配优化 (Position/Length) - Top10 → Top5
"""
from typing import List, Dict, Any

from src.core.config import RERANK_CONFIG
from src.core.logging import get_logger

logger = get_logger(__name__)


class StageOneReranker:
    """
    一阶：轻量级预排序
    使用轻量级模型快速筛选
    """

    def __init__(self):
        self.model = None  # BGE-small
        self.top_k = RERANK_CONFIG["stage1"]["top_k"]

    async def rerank(
        self,
        query: str,
        candidates: List[Dict[str, Any]],
        top_k: int | None = None,
    ) -> List[Dict[str, Any]]:
        """预排序"""
        logger.debug(f"Stage 1: Reranking {len(candidates)} candidates")

        limit = max(self.top_k, top_k or 0)
        sorted_candidates = sorted(
            candidates,
            key=lambda x: x.get("score", 0),
            reverse=True
        )

        return sorted_candidates[:limit]


class StageTwoReranker:
    """
    二阶：核心精排
    使用更强的重排序模型
    """

    def __init__(self):
        self.model = None  # BGE-Reranker-large
        self.top_k = RERANK_CONFIG["stage2"]["top_k"]

    async def rerank(
        self,
        query: str,
        candidates: List[Dict[str, Any]],
        top_k: int | None = None,
    ) -> List[Dict[str, Any]]:
        """核心精排"""
        logger.debug(f"Stage 2: Reranking {len(candidates)} candidates")

        limit = max(self.top_k, top_k or 0)
        reranked = sorted(
            candidates,
            key=lambda x: (
                x.get("score", 0),
                x.get("metadata", {}).get("path", ""),
                x.get("id", ""),
            ),
            reverse=True,
        )

        return reranked[:limit]


class StageThreeOptimizer:
    """
    三阶：生成适配优化
    - 位置重排：把重要文档放前面
    - 去重：相似文档合并
    - 长度截断：控制总长度
    """

    def __init__(self):
        self.max_length = RERANK_CONFIG["stage3"]["max_context_length"]
        self.deduplicate = RERANK_CONFIG["stage3"]["deduplication"]

    async def optimize(
        self,
        query: str,
        candidates: List[Dict[str, Any]],
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """生成适配优化"""
        logger.debug(f"Stage 3: Optimizing {len(candidates)} candidates")

        results = candidates

        if self.deduplicate:
            results = self._deduplicate(results)

        results = self._optimize_position(results)
        results = self._truncate_by_length(results, self.max_length)

        return results[:top_k]

    def _deduplicate(
        self,
        candidates: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """去重：基于内容相似度"""
        seen = set()
        unique = []

        for c in candidates:
            content_hash = hash(c.get("content", "")[:100])
            if content_hash not in seen:
                seen.add(content_hash)
                unique.append(c)

        return unique

    def _optimize_position(
        self,
        candidates: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        位置优化
        LLM对开头和结尾位置注意力更高
        """
        if len(candidates) < 3:
            return candidates

        optimized = candidates.copy()
        return optimized

    def _truncate_by_length(
        self,
        candidates: List[Dict[str, Any]],
        max_length: int
    ) -> List[Dict[str, Any]]:
        """按长度截断"""
        total_length = 0
        truncated = []

        for c in candidates:
            content_length = len(c.get("content", ""))
            if total_length + content_length > max_length:
                remaining = max_length - total_length
                if remaining > 100:
                    c["content"] = c["content"][:remaining]
                    truncated.append(c)
                break

            total_length += content_length
            truncated.append(c)

        return truncated


class ThreeStageReranker:
    """
    三阶重排序器
    组合三个阶段的排序
    """

    def __init__(self):
        self.stage1 = StageOneReranker()
        self.stage2 = StageTwoReranker()
        self.stage3 = StageThreeOptimizer()

    async def rerank(
        self,
        query: str,
        candidates: List[Dict[str, Any]],
        top_k: int = 5,
        apply_generation_optimization: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        执行三阶重排序

        流程：
        1. Stage 1: 快速筛选 Top100 -> Top30
        2. Stage 2: 精排 Top30 -> Top10
        3. Stage 3: 生成优化 Top10 -> Top5
        """
        if not candidates:
            return []

        logger.info(f"Starting three-stage reranking for {len(candidates)} candidates")

        stage1_results = await self.stage1.rerank(query, candidates)
        logger.debug(f"Stage 1: {len(candidates)} -> {len(stage1_results)}")

        stage2_results = await self.stage2.rerank(query, stage1_results)
        logger.debug(f"Stage 2: {len(stage1_results)} -> {len(stage2_results)}")

        if not apply_generation_optimization:
            return stage2_results[:top_k]

        final_results = await self.stage3.optimize(query, stage2_results, top_k)
        logger.debug(f"Stage 3: {len(stage2_results)} -> {len(final_results)}")

        return final_results

