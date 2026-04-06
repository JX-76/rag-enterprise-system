"""
Celery异步任务队列
处理耗时的文档处理和向量化任务
"""
from celery import Celery
from typing import List
import logging

logger = logging.getLogger(__name__)

# 创建Celery应用
app = Celery(
    'rag_tasks',
    broker='redis://localhost:6379/0',
    backend='redis://localhost:6379/0',
    include=['src.workflow.tasks']
)

# 配置
app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Asia/Shanghai',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1小时超时
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
)


# 任务定义
@app.task(bind=True, max_retries=3)
def process_document_task(self, file_path: str, metadata: dict = None):
    """
    异步处理文档任务
    
    流程:
    1. 下载/读取文档
    2. 解析文档
    3. 分块
    4. 向量化
    5. 存储到向量数据库
    """
    try:
        logger.info(f"开始处理文档: {file_path}")
        
        # 导入处理模块
        from src.ingestion.document_parser import DocumentParser
        from src.ingestion.parent_child_chunker import ParentChildChunker
        from src.services.embedding_service import EmbeddingService, VectorStore
        
        # 1. 解析文档
        parser = DocumentParser()
        doc = parser.parse(file_path)
        
        # 2. 分块
        chunker = ParentChildChunker()
        parent_chunks = chunker.chunk(doc.get_full_text())
        
        # 3. 收集所有子块
        all_chunks = []
        for parent in parent_chunks:
            all_chunks.extend(parent.child_chunks)
        
        # 4. 向量化
        embedder = EmbeddingService()
        texts = [c.content for c in all_chunks]
        embeddings = embedder.encode(texts)
        
        # 5. 存储
        store = VectorStore()
        documents = [{
            "id": f"chunk_{i}",
            "text": c.content,
            "metadata": {**c.metadata, **(metadata or {})}
        } for i, c in enumerate(all_chunks)]
        
        store.add_documents(documents, embeddings)
        
        logger.info(f"文档处理完成: {len(all_chunks)} 个分块")
        return {
            "status": "success",
            "num_chunks": len(all_chunks),
            "file_path": file_path
        }
        
    except Exception as exc:
        logger.error(f"文档处理失败: {exc}")
        # 重试
        raise self.retry(exc=exc, countdown=60)


@app.task(bind=True)
def cleanup_old_documents_task(self, days: int = 30):
    """
    清理过期文档
    
    定时任务，清理30天前的文档
    """
    try:
        logger.info(f"开始清理{days}天前的文档")
        # 实现清理逻辑
        return {"status": "success", "deleted_count": 0}
    except Exception as exc:
        logger.error(f"清理失败: {exc}")
        raise self.retry(exc=exc, countdown=300)


if __name__ == '__main__':
    app.start()
