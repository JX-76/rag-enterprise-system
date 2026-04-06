"""
Dual Index Manager - 双索引热切换
解决HNSW不支持高效增量更新的问题
主索引对外服务，备索引后台重建，原子切换
"""
import asyncio
import os
import pickle
import shutil
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable
import numpy as np

from src.core.logging import get_logger

logger = get_logger(__name__)


class IndexState(Enum):
    """索引状态"""
    ACTIVE = "active"           # 正在服务
    BUILDING = "building"       # 后台重建中
    READY = "ready"             # 重建完成，待切换
    STALE = "stale"             # 已过期，待清理


@dataclass
class IndexMetadata:
    """索引元数据"""
    id: str
    state: IndexState
    created_at: datetime
    document_count: int
    vector_dimension: int
    index_type: str
    file_path: Path
    version: int = 1


class DualIndexManager:
    """
    双索引管理器
    
    工作流程：
    1. 主索引 (Primary) - 对外提供查询服务
    2. 备索引 (Secondary) - 后台异步重建新索引
    3. 切换 (Switch) - 原子操作切换主备指针
    4. 清理 (Cleanup) - 归档旧索引
    
    优势：
    - 零停机更新
    - 原子切换保证一致性
    - 支持快速回滚
    """
    
    def __init__(
        self,
        index_dir: str = "./data/vector_index/dual",
        index_builder: Optional[Callable] = None,
        max_versions: int = 3
    ):
        self.index_dir = Path(index_dir)
        self.index_dir.mkdir(parents=True, exist_ok=True)
        
        self.index_builder = index_builder
        self.max_versions = max_versions
        
        # 双索引指针
        self._primary: Optional[Any] = None      # 当前服务索引
        self._secondary: Optional[Any] = None    # 后台重建索引
        
        # 元数据
        self._primary_meta: Optional[IndexMetadata] = None
        self._secondary_meta: Optional[IndexMetadata] = None
        
        # 锁
        self._switch_lock = asyncio.Lock()
        self._build_lock = asyncio.Lock()
        
        # 状态
        self._is_building = False
        
        logger.info(f"DualIndexManager initialized: {index_dir}")
    
    async def initialize(self, initial_index: Any, metadata: Dict = None):
        """初始化主索引"""
        self._primary = initial_index
        self._primary_meta = IndexMetadata(
            id=f"idx_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            state=IndexState.ACTIVE,
            created_at=datetime.now(),
            document_count=metadata.get("count", 0) if metadata else 0,
            vector_dimension=metadata.get("dim", 0) if metadata else 0,
            index_type="hnsw",
            file_path=self.index_dir / "primary.index",
            version=1
        )
        
        # 保存初始索引
        await self._save_index(self._primary, self._primary_meta.file_path)
        
        logger.info(
            f"Primary index initialized: "
            f"{self._primary_meta.document_count} docs, "
            f"v{self._primary_meta.version}"
        )
    
    async def _save_index(self, index: Any, path: Path):
        """保存索引到磁盘"""
        try:
            with open(path, 'wb') as f:
                pickle.dump(index, f)
            logger.debug(f"Index saved: {path}")
        except Exception as e:
            logger.error(f"Failed to save index: {e}")
            raise
    
    async def _load_index(self, path: Path) -> Any:
        """从磁盘加载索引"""
        try:
            with open(path, 'rb') as f:
                index = pickle.load(f)
            logger.debug(f"Index loaded: {path}")
            return index
        except Exception as e:
            logger.error(f"Failed to load index: {e}")
            raise
    
    async def rebuild_index(
        self,
        documents: List[Dict],
        embedding_func: Callable,
        metadata: Optional[Dict] = None
    ) -> bool:
        """
        后台重建索引
        
        Args:
            documents: 新文档列表
            embedding_func: 嵌入函数
            metadata: 额外元数据
        
        Returns:
            是否成功
        """
        async with self._build_lock:
            if self._is_building:
                logger.warning("Index rebuild already in progress")
                return False
            
            self._is_building = True
            logger.info(f"Starting index rebuild: {len(documents)} documents")
            
            try:
                # 生成新索引ID
                new_version = (self._primary_meta.version + 1) if self._primary_meta else 1
                new_id = f"idx_{datetime.now().strftime('%Y%m%d_%H%M%S')}_v{new_version}"
                
                # 创建新索引元数据
                self._secondary_meta = IndexMetadata(
                    id=new_id,
                    state=IndexState.BUILDING,
                    created_at=datetime.now(),
                    document_count=len(documents),
                    vector_dimension=metadata.get("dim", 0) if metadata else 0,
                    index_type="hnsw",
                    file_path=self.index_dir / f"secondary_{new_id}.index",
                    version=new_version
                )
                
                # 后台构建索引
                if self.index_builder:
                    self._secondary = await asyncio.to_thread(
                        self.index_builder,
                        documents,
                        embedding_func
                    )
                else:
                    # 默认使用FAISS构建
                    self._secondary = await self._build_faiss_index(
                        documents,
                        embedding_func
                    )
                
                # 保存新索引
                await self._save_index(self._secondary, self._secondary_meta.file_path)
                
                # 标记为就绪
                self._secondary_meta.state = IndexState.READY
                
                logger.info(
                    f"Index rebuild completed: {new_id}, "
                    f"{len(documents)} documents"
                )
                
                return True
                
            except Exception as e:
                logger.error(f"Index rebuild failed: {e}")
                self._secondary = None
                self._secondary_meta = None
                return False
            finally:
                self._is_building = False
    
    async def _build_faiss_index(
        self,
        documents: List[Dict],
        embedding_func: Callable
    ) -> Any:
        """构建FAISS索引"""
        try:
            import faiss
            
            # 生成嵌入
            texts = [doc.get("content", "") for doc in documents]
            embeddings = await asyncio.to_thread(embedding_func, texts)
            
            if len(embeddings) == 0:
                return None
            
            dim = len(embeddings[0])
            
            # 创建HNSW索引
            index = faiss.IndexHNSWFlat(dim, 32)
            index.hnsw.efConstruction = 128
            
            # 添加向量
            embeddings_np = np.array(embeddings).astype('float32')
            index.add(embeddings_np)
            
            return {
                "index": index,
                "documents": documents,
                "dim": dim,
                "count": len(documents)
            }
            
        except ImportError:
            logger.error("FAISS not available")
            raise
    
    async def switch_index(self) -> bool:
        """
        原子切换主备索引
        
        流程：
        1. 检查备索引是否就绪
        2. 原子切换指针
        3. 旧主索引降级为STALE
        4. 清理历史版本
        """
        async with self._switch_lock:
            if not self._secondary or not self._secondary_meta:
                logger.warning("No secondary index available for switch")
                return False
            
            if self._secondary_meta.state != IndexState.READY:
                logger.warning(f"Secondary index not ready: {self._secondary_meta.state}")
                return False
            
            logger.info(f"Switching index: v{self._primary_meta.version} -> v{self._secondary_meta.version}")
            
            try:
                # 原子切换
                old_primary = self._primary
                old_primary_meta = self._primary_meta
                
                self._primary = self._secondary
                self._primary_meta = self._secondary_meta
                self._primary_meta.state = IndexState.ACTIVE
                
                self._secondary = None
                self._secondary_meta = None
                
                # 旧索引标记为过期
                if old_primary_meta:
                    old_primary_meta.state = IndexState.STALE
                    await self._archive_index(old_primary_meta)
                
                # 清理历史版本
                await self._cleanup_old_versions()
                
                logger.info(
                    f"Index switched successfully: "
                    f"now serving v{self._primary_meta.version}"
                )
                
                return True
                
            except Exception as e:
                logger.error(f"Index switch failed: {e}")
                return False
    
    async def _archive_index(self, metadata: IndexMetadata):
        """归档旧索引"""
        archive_dir = self.index_dir / "archive"
        archive_dir.mkdir(exist_ok=True)
        
        archive_path = archive_dir / f"{metadata.id}.index"
        
        try:
            if metadata.file_path.exists():
                shutil.move(str(metadata.file_path), str(archive_path))
                logger.debug(f"Index archived: {metadata.id}")
        except Exception as e:
            logger.warning(f"Failed to archive index {metadata.id}: {e}")
    
    async def _cleanup_old_versions(self):
        """清理旧版本索引"""
        archive_dir = self.index_dir / "archive"
        if not archive_dir.exists():
            return
        
        try:
            archives = sorted(
                archive_dir.glob("*.index"),
                key=lambda p: p.stat().st_mtime,
                reverse=True
            )
            
            # 保留最近N个版本
            for old_file in archives[self.max_versions:]:
                old_file.unlink()
                logger.debug(f"Cleaned up old index: {old_file.name}")
                
        except Exception as e:
            logger.warning(f"Cleanup failed: {e}")
    
    def get_active_index(self) -> Optional[Any]:
        """获取当前服务索引"""
        return self._primary
    
    def get_index_metadata(self) -> Optional[IndexMetadata]:
        """获取当前索引元数据"""
        return self._primary_meta
    
    async def search(
        self,
        query_vector: np.ndarray,
        top_k: int = 10,
        **kwargs
    ) -> List[Dict]:
        """
        搜索当前活跃索引
        
        保证原子性：切换期间查询不会被中断
        """
        async with self._switch_lock:
            if not self._primary:
                raise RuntimeError("No active index available")
            
            # 执行搜索
            if isinstance(self._primary, dict) and "index" in self._primary:
                # FAISS索引格式
                index = self._primary["index"]
                documents = self._primary["documents"]
                
                query_np = np.array([query_vector]).astype('float32')
                distances, indices = index.search(query_np, top_k)
                
                results = []
                for i, idx in enumerate(indices[0]):
                    if idx >= 0 and idx < len(documents):
                        doc = documents[idx].copy()
                        doc["score"] = float(1 / (1 + distances[0][i]))  # 转换为相似度
                        doc["index_version"] = self._primary_meta.version if self._primary_meta else 0
                        results.append(doc)
                
                return results
            else:
                # 自定义索引格式
                return await self._custom_search(query_vector, top_k, **kwargs)
    
    async def _custom_search(
        self,
        query_vector: np.ndarray,
        top_k: int,
        **kwargs
    ) -> List[Dict]:
        """自定义索引搜索（由用户提供）"""
        raise NotImplementedError("Custom search not implemented")
    
    async def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            "primary": {
                "version": self._primary_meta.version if self._primary_meta else 0,
                "documents": self._primary_meta.document_count if self._primary_meta else 0,
                "state": self._primary_meta.state.value if self._primary_meta else "unknown",
                "created_at": self._primary_meta.created_at.isoformat() if self._primary_meta else None
            },
            "secondary": {
                "version": self._secondary_meta.version if self._secondary_meta else 0,
                "documents": self._secondary_meta.document_count if self._secondary_meta else 0,
                "state": self._secondary_meta.state.value if self._secondary_meta else "none",
                "is_building": self._is_building
            },
            "max_versions": self.max_versions
        }


class IncrementalIndexUpdater:
    """
    增量索引更新器
    
    结合双索引 + 增量更新策略：
    1. 小批量更新 → 直接修改活跃索引
    2. 大批量更新 → 触发后台重建 + 热切换
    """
    
    def __init__(
        self,
        dual_manager: DualIndexManager,
        batch_threshold: int = 1000
    ):
        self.dual_manager = dual_manager
        self.batch_threshold = batch_threshold
        
        self._update_queue = []
        self._lock = asyncio.Lock()
    
    async def add_documents(
        self,
        documents: List[Dict],
        embedding_func: Callable
    ) -> bool:
        """
        添加文档到索引
        
        策略：
        - < batch_threshold: 增量添加到当前索引
        - >= batch_threshold: 触发重建+切换
        """
        if len(documents) < self.batch_threshold:
            # 小批量：增量更新
            return await self._incremental_add(documents, embedding_func)
        else:
            # 大批量：重建+切换
            success = await self.dual_manager.rebuild_index(
                documents,
                embedding_func
            )
            if success:
                return await self.dual_manager.switch_index()
            return False
    
    async def _incremental_add(
        self,
        documents: List[Dict],
        embedding_func: Callable
    ) -> bool:
        """增量添加（需要索引支持）"""
        # 获取当前索引
        current = self.dual_manager.get_active_index()
        if not current:
            return False
        
        try:
            import faiss
            import numpy as np
            
            if isinstance(current, dict) and "index" in current:
                index = current["index"]
                existing_docs = current["documents"]
                
                # 生成嵌入
                texts = [doc.get("content", "") for doc in documents]
                embeddings = await asyncio.to_thread(embedding_func, texts)
                
                # 添加到索引
                embeddings_np = np.array(embeddings).astype('float32')
                index.add(embeddings_np)
                
                # 更新文档列表
                existing_docs.extend(documents)
                current["count"] = len(existing_docs)
                
                # 更新元数据
                meta = self.dual_manager.get_index_metadata()
                if meta:
                    meta.document_count = len(existing_docs)
                
                logger.info(f"Incrementally added {len(documents)} documents")
                return True
                
        except Exception as e:
            logger.error(f"Incremental add failed: {e}")
            return False
    
    async def delete_documents(self, doc_ids: List[str]) -> bool:
        """
        删除文档（软删除）
        
        HNSW不支持硬删除，使用标记删除
        """
        current = self.dual_manager.get_active_index()
        if not current or not isinstance(current, dict):
            return False
        
        documents = current.get("documents", [])
        deleted_count = 0
        
        for doc in documents:
            if doc.get("id") in doc_ids:
                doc["_deleted"] = True
                deleted_count += 1
        
        logger.info(f"Soft deleted {deleted_count} documents")
        return deleted_count > 0
