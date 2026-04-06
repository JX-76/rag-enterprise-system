"""
Incremental Index Update - 增量索引更新
支持实时更新、版本管理、数据同步
"""
import asyncio
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import hashlib
import json
import aiofiles

from src.core.logging import get_logger
from src.services.embedding_service import get_embedding_service
from src.vector_store.faiss_store import get_vector_store
from src.ingestion.pipeline import Document, DocumentProcessor

logger = get_logger(__name__)


@dataclass
class DocumentVersion:
    """文档版本"""
    doc_id: str
    content_hash: str
    updated_at: datetime
    version: int = 1


class IncrementalIndexer:
    """
    增量索引管理器
    
    功能：
    1. 检测变更（新增/修改/删除）
    2. 局部更新索引
    3. 版本追踪
    4. 自动同步
    """
    
    def __init__(
        self,
        index_dir: str = "./data/index",
        sync_interval: int = 60
    ):
        self.index_dir = Path(index_dir)
        self.index_dir.mkdir(parents=True, exist_ok=True)
        
        self.versions_file = self.index_dir / "versions.json"
        self.processor = DocumentProcessor()
        self.sync_interval = sync_interval
        
        # 内存中的版本缓存
        self._versions: Dict[str, DocumentVersion] = {}
        self._lock = asyncio.Lock()
        
        # 加载历史版本
        self._load_versions()
    
    def _load_versions(self):
        """加载版本记录"""
        if self.versions_file.exists():
            try:
                with open(self.versions_file, 'r') as f:
                    data = json.load(f)
                    for doc_id, v in data.items():
                        self._versions[doc_id] = DocumentVersion(
                            doc_id=doc_id,
                            content_hash=v['content_hash'],
                            updated_at=datetime.fromisoformat(v['updated_at']),
                            version=v['version']
                        )
                logger.info(f"Loaded {len(self._versions)} document versions")
            except Exception as e:
                logger.error(f"Failed to load versions: {e}")
    
    async def _save_versions(self):
        """保存版本记录"""
        async with self._lock:
            data = {
                doc_id: {
                    'content_hash': v.content_hash,
                    'updated_at': v.updated_at.isoformat(),
                    'version': v.version
                }
                for doc_id, v in self._versions.items()
            }
            
            async with aiofiles.open(self.versions_file, 'w') as f:
                await f.write(json.dumps(data, indent=2))
    
    def _compute_hash(self, content: str) -> str:
        """计算内容哈希"""
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    async def detect_changes(
        self,
        documents: List[Document]
    ) -> Dict[str, List[Document]]:
        """
        检测变更
        
        Returns:
            {
                'new': [],      # 新增文档
                'updated': [],  # 修改的文档
                'unchanged': [], # 未变更的文档
                'deleted': []   # 已删除的文档ID（需外部提供全量列表对比）
            }
        """
        changes = {
            'new': [],
            'updated': [],
            'unchanged': [],
            'deleted': []
        }
        
        current_ids: Set[str] = set()
        
        for doc in documents:
            current_ids.add(doc.id)
            content_hash = self._compute_hash(doc.content)
            
            if doc.id not in self._versions:
                # 新文档
                changes['new'].append(doc)
            elif self._versions[doc.id].content_hash != content_hash:
                # 文档已修改
                changes['updated'].append(doc)
            else:
                # 未变更
                changes['unchanged'].append(doc)
        
        # 检测删除的文档
        existing_ids = set(self._versions.keys())
        deleted_ids = existing_ids - current_ids
        changes['deleted'] = list(deleted_ids)
        
        logger.info(
            f"Change detection: new={len(changes['new'])}, "
            f"updated={len(changes['updated'])}, "
            f"unchanged={len(changes['unchanged'])}, "
            f"deleted={len(changes['deleted'])}"
        )
        
        return changes
    
    async def update(
        self,
        documents: List[Document],
        batch_size: int = 32
    ) -> Dict[str, Any]:
        """
        执行增量更新
        
        Args:
            documents: 新文档列表
            batch_size: 批处理大小
        
        Returns:
            更新统计
        """
        stats = {
            'added': 0,
            'updated': 0,
            'deleted': 0,
            'unchanged': 0,
            'errors': 0
        }
        
        # 检测变更
        changes = await self.detect_changes(documents)
        
        embedding_service = get_embedding_service()
        vector_store = get_vector_store()
        
        # 处理新增文档
        if changes['new']:
            added = await self._process_documents(
                changes['new'],
                embedding_service,
                vector_store,
                batch_size
            )
            stats['added'] = added
        
        # 处理更新的文档
        if changes['updated']:
            # 先删除旧版本
            await self._delete_documents(changes['updated'], vector_store)
            # 再添加新版本
            updated = await self._process_documents(
                changes['updated'],
                embedding_service,
                vector_store,
                batch_size
            )
            stats['updated'] = updated
        
        # 处理删除的文档
        if changes['deleted']:
            deleted_count = await self._delete_by_ids(
                changes['deleted'],
                vector_store
            )
            stats['deleted'] = deleted_count
        
        stats['unchanged'] = len(changes['unchanged'])
        
        # 保存版本记录
        await self._save_versions()
        
        logger.info(f"Incremental update complete: {stats}")
        return stats
    
    async def _process_documents(
        self,
        documents: List[Document],
        embedding_service,
        vector_store,
        batch_size: int
    ) -> int:
        """处理文档批次"""
        processed = 0
        
        for i in range(0, len(documents), batch_size):
            batch = documents[i:i + batch_size]
            
            try:
                # 生成embeddings
                texts = [doc.content for doc in batch]
                embeddings = await embedding_service.encode(texts)
                
                # 写入向量库
                await vector_store.add(
                    documents=[
                        {"id": doc.id, "content": doc.content, "metadata": doc.metadata}
                        for doc in batch
                    ],
                    embeddings=embeddings
                )
                
                # 更新版本记录
                for doc in batch:
                    content_hash = self._compute_hash(doc.content)
                    
                    if doc.id in self._versions:
                        old_version = self._versions[doc.id].version
                        self._versions[doc.id] = DocumentVersion(
                            doc_id=doc.id,
                            content_hash=content_hash,
                            updated_at=datetime.now(),
                            version=old_version + 1
                        )
                    else:
                        self._versions[doc.id] = DocumentVersion(
                            doc_id=doc.id,
                            content_hash=content_hash,
                            updated_at=datetime.now(),
                            version=1
                        )
                
                processed += len(batch)
                
            except Exception as e:
                logger.error(f"Failed to process batch: {e}")
        
        return processed
    
    async def _delete_documents(
        self,
        documents: List[Document],
        vector_store
    ):
        """删除指定文档"""
        ids = [doc.id for doc in documents]
        await self._delete_by_ids(ids, vector_store)
    
    async def _delete_by_ids(
        self,
        ids: List[str],
        vector_store
    ) -> int:
        """按ID删除"""
        try:
            await vector_store.delete(ids)
            
            # 更新版本记录
            for doc_id in ids:
                if doc_id in self._versions:
                    del self._versions[doc_id]
            
            return len(ids)
        except Exception as e:
            logger.error(f"Failed to delete documents: {e}")
            return 0
    
    async def sync_directory(
        self,
        directory: str,
        pattern: str = "*.txt",
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        同步整个目录
        
        自动检测文件变更并增量更新
        """
        dir_path = Path(directory)
        if not dir_path.exists():
            raise FileNotFoundError(f"Directory not found: {directory}")
        
        # 扫描文件
        files = list(dir_path.glob(pattern))
        logger.info(f"Found {len(files)} files matching {pattern}")
        
        # 加载文档
        documents = []
        for file_path in files:
            try:
                content = file_path.read_text(encoding='utf-8')
                docs = self.processor.process(
                    content=content,
                    source=str(file_path),
                    metadata={**(metadata or {}), 'filename': file_path.name}
                )
                documents.extend(docs)
            except Exception as e:
                logger.error(f"Failed to load {file_path}: {e}")
        
        # 执行增量更新
        return await self.update(documents)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取索引统计"""
        return {
            'total_documents': len(self._versions),
            'last_sync': max(
                (v.updated_at for v in self._versions.values()),
                default=None
            )
        }


# 全局实例
_incremental_indexer: Optional[IncrementalIndexer] = None


async def get_incremental_indexer() -> IncrementalIndexer:
    """获取全局增量索引器"""
    global _incremental_indexer
    if _incremental_indexer is None:
        _incremental_indexer = IncrementalIndexer()
    return _incremental_indexer
