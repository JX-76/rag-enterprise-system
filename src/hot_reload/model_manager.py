"""
Hot Reload Manager - 模型热更新管理器
支持模型动态切换、版本管理、A/B测试
"""
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from datetime import datetime
import asyncio
import json
from pathlib import Path
from enum import Enum
import threading

from src.core.logging import get_logger

logger = get_logger(__name__)


class ModelStatus(Enum):
    """模型状态"""
    LOADING = "loading"
    ACTIVE = "active"
    DEGRADED = "degraded"
    FAILED = "failed"
    UNLOADING = "unloading"


@dataclass
class ModelVersion:
    """模型版本"""
    id: str
    name: str
    version: str
    path: str
    status: ModelStatus
    config: Dict[str, Any]
    created_at: datetime
    loaded_at: Optional[datetime] = None
    metadata: Dict[str, Any] = None


class HotReloadManager:
    """
    模型热更新管理器
    
    功能：
    1. 模型版本管理
    2. 动态加载/卸载
    3. A/B测试流量分配
    4. 灰度发布
    5. 自动回滚
    """
    
    def __init__(self, models_dir: str = "./models"):
        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(parents=True, exist_ok=True)
        
        self._models: Dict[str, ModelVersion] = {}
        self._active_model: Optional[str] = None
        self._traffic_split: Dict[str, float] = {}  # model_id -> percentage
        self._model_instances: Dict[str, Any] = {}
        self._lock = asyncio.Lock()
        self._health_checks: Dict[str, Callable] = {}
    
    async def register_model(
        self,
        model_id: str,
        name: str,
        version: str,
        path: str,
        config: Optional[Dict] = None
    ) -> ModelVersion:
        """注册模型"""
        model = ModelVersion(
            id=model_id,
            name=name,
            version=version,
            path=path,
            status=ModelStatus.LOADING,
            config=config or {},
            created_at=datetime.now()
        )
        
        async with self._lock:
            self._models[model_id] = model
        
        logger.info(f"Registered model: {model_id} ({name}@{version})")
        return model
    
    async def load_model(self, model_id: str) -> bool:
        """加载模型"""
        if model_id not in self._models:
            logger.error(f"Model not found: {model_id}")
            return False
        
        model = self._models[model_id]
        model.status = ModelStatus.LOADING
        
        try:
            # 这里应该调用具体的模型加载逻辑
            # 简化实现：模拟加载
            await asyncio.sleep(0.1)
            
            model.status = ModelStatus.ACTIVE
            model.loaded_at = datetime.now()
            
            logger.info(f"Model loaded: {model_id}")
            return True
            
        except Exception as e:
            model.status = ModelStatus.FAILED
            logger.error(f"Failed to load model {model_id}: {e}")
            return False
    
    async def unload_model(self, model_id: str) -> bool:
        """卸载模型"""
        if model_id not in self._models:
            return False
        
        model = self._models[model_id]
        model.status = ModelStatus.UNLOADING
        
        try:
            # 清理模型实例
            if model_id in self._model_instances:
                del self._model_instances[model_id]
            
            model.status = ModelStatus.FAILED  # 或者设为 None
            logger.info(f"Model unloaded: {model_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to unload model {model_id}: {e}")
            return False
    
    async def switch_model(self, model_id: str) -> bool:
        """切换活跃模型"""
        if model_id not in self._models:
            logger.error(f"Model not found: {model_id}")
            return False
        
        model = self._models[model_id]
        
        # 如果模型未加载，先加载
        if model.status != ModelStatus.ACTIVE:
            if not await self.load_model(model_id):
                return False
        
        async with self._lock:
            old_model = self._active_model
            self._active_model = model_id
            # 重置流量分配
            self._traffic_split = {model_id: 100.0}
        
        logger.info(f"Switched model: {old_model} -> {model_id}")
        return True
    
    async def set_traffic_split(self, splits: Dict[str, float]):
        """设置流量分配"""
        total = sum(splits.values())
        if abs(total - 100) > 0.01:
            raise ValueError(f"Traffic splits must sum to 100, got {total}")
        
        async with self._lock:
            self._traffic_split = splits
        
        logger.info(f"Traffic split updated: {splits}")
    
    def get_model_for_request(self, user_id: Optional[str] = None) -> Optional[str]:
        """为请求分配模型"""
        if not self._traffic_split:
            return self._active_model
        
        # 如果有用户ID，使用一致性哈希
        if user_id:
            import hashlib
            hash_value = int(hashlib.md5(user_id.encode()).hexdigest(), 16)
            bucket = hash_value % 100
            
            cumulative = 0
            for model_id, percentage in self._traffic_split.items():
                cumulative += percentage
                if bucket < cumulative:
                    return model_id
        
        # 随机分配
        import random
        r = random.random() * 100
        cumulative = 0
        for model_id, percentage in self._traffic_split.items():
            cumulative += percentage
            if r < cumulative:
                return model_id
        
        return self._active_model
    
    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        results = {}
        
        for model_id, model in self._models.items():
            # 执行健康检查
            check_func = self._health_checks.get(model_id)
            
            if check_func:
                try:
                    is_healthy = await check_func()
                    if not is_healthy:
                        model.status = ModelStatus.DEGRADED
                except Exception as e:
                    logger.error(f"Health check failed for {model_id}: {e}")
                    model.status = ModelStatus.DEGRADED
            
            results[model_id] = {
                "status": model.status.value,
                "loaded_at": model.loaded_at.isoformat() if model.loaded_at else None
            }
        
        return results
    
    async def rollback(self) -> bool:
        """回滚到上一个版本"""
        # 简化实现：切换到第一个可用的非活跃模型
        for model_id, model in self._models.items():
            if model_id != self._active_model and model.status == ModelStatus.ACTIVE:
                return await self.switch_model(model_id)
        
        logger.warning("No previous model available for rollback")
        return False
    
    def get_active_model(self) -> Optional[ModelVersion]:
        """获取当前活跃模型"""
        if self._active_model and self._active_model in self._models:
            return self._models[self._active_model]
        return None
    
    def list_models(self) -> List[ModelVersion]:
        """列出所有模型"""
        return list(self._models.values())


# 全局实例
_hot_reload_manager: Optional[HotReloadManager] = None


def get_hot_reload_manager() -> HotReloadManager:
    """获取全局热更新管理器"""
    global _hot_reload_manager
    if _hot_reload_manager is None:
        _hot_reload_manager = HotReloadManager()
    return _hot_reload_manager
