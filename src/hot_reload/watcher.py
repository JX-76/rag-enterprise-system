"""
Model Watcher - 模型文件监控
监控模型文件变化，自动触发更新
"""
import asyncio
from pathlib import Path
from typing import Optional, Callable, List
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileModifiedEvent, FileCreatedEvent
import time

from src.core.logging import get_logger

logger = get_logger(__name__)


class ModelChangeHandler(FileSystemEventHandler):
    """模型文件变化处理器"""
    
    def __init__(self, callback: Callable[[str], None]):
        self.callback = callback
        self._last_modified: dict = {}
        self._debounce_seconds = 2
    
    def on_modified(self, event):
        if event.is_directory:
            return
        
        # 防抖
        current_time = time.time()
        file_path = str(event.src_path)
        
        if file_path in self._last_modified:
            if current_time - self._last_modified[file_path] < self._debounce_seconds:
                return
        
        self._last_modified[file_path] = current_time
        
        logger.info(f"Model file modified: {file_path}")
        self.callback(file_path)
    
    def on_created(self, event):
        if event.is_directory:
            return
        
        file_path = str(event.src_path)
        logger.info(f"Model file created: {file_path}")
        self.callback(file_path)


class ModelWatcher:
    """
    模型文件监控器
    
    功能：
    1. 监控模型目录变化
    2. 自动触发模型重载
    3. 支持防抖
    """
    
    def __init__(self, models_dir: str = "./models"):
        self.models_dir = Path(models_dir)
        self.observer: Optional[Observer] = None
        self._handlers: List[Callable] = []
        self._running = False
    
    def add_handler(self, handler: Callable[[str], None]):
        """添加变化处理器"""
        self._handlers.append(handler)
    
    def _on_file_change(self, file_path: str):
        """文件变化回调"""
        for handler in self._handlers:
            try:
                handler(file_path)
            except Exception as e:
                logger.error(f"Handler failed: {e}")
    
    def start(self):
        """启动监控"""
        if self._running:
            return
        
        self.models_dir.mkdir(parents=True, exist_ok=True)
        
        event_handler = ModelChangeHandler(self._on_file_change)
        self.observer = Observer()
        self.observer.schedule(event_handler, str(self.models_dir), recursive=True)
        self.observer.start()
        
        self._running = True
        logger.info(f"Model watcher started: {self.models_dir}")
    
    def stop(self):
        """停止监控"""
        if not self._running:
            return
        
        if self.observer:
            self.observer.stop()
            self.observer.join()
        
        self._running = False
        logger.info("Model watcher stopped")
    
    async def watch_async(self):
        """异步监控（用于协程环境）"""
        self.start()
        
        try:
            while self._running:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            self.stop()
