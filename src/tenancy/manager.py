"""
Tenant Manager - 多租户管理器
支持租户隔离、资源配额、权限管理
"""
from typing import Dict, Optional, Any, List
from dataclasses import dataclass, field
from datetime import datetime
import asyncio
import json
from pathlib import Path

from src.core.logging import get_logger
from src.core.config import settings

logger = get_logger(__name__)


@dataclass
class TenantQuota:
    """租户资源配额"""
    max_requests_per_minute: int = 100
    max_tokens_per_day: int = 100000
    max_documents: int = 1000
    max_storage_mb: int = 100
    max_concurrent_queries: int = 5


@dataclass
class Tenant:
    """租户对象"""
    id: str
    name: str
    api_key: str
    quota: TenantQuota = field(default_factory=TenantQuota)
    config: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    is_active: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


class TenantManager:
    """
    租户管理器
    
    功能：
    1. 租户CRUD
    2. API Key验证
    3. 资源配额管理
    4. 使用量统计
    """
    
    def __init__(self, storage_path: Optional[str] = None):
        self.storage_path = storage_path or "./data/tenants.json"
        self._tenants: Dict[str, Tenant] = {}
        self._api_key_map: Dict[str, str] = {}  # api_key -> tenant_id
        self._usage_stats: Dict[str, Dict] = {}
        self._lock = asyncio.Lock()
        self._load_tenants()
    
    def _load_tenants(self):
        """从文件加载租户"""
        try:
            path = Path(self.storage_path)
            if path.exists():
                with open(path, 'r') as f:
                    data = json.load(f)
                    for tenant_data in data.get('tenants', []):
                        tenant = self._dict_to_tenant(tenant_data)
                        self._tenants[tenant.id] = tenant
                        self._api_key_map[tenant.api_key] = tenant.id
                logger.info(f"Loaded {len(self._tenants)} tenants")
        except Exception as e:
            logger.error(f"Failed to load tenants: {e}")
    
    def _save_tenants(self):
        """保存租户到文件"""
        try:
            path = Path(self.storage_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            
            data = {
                'tenants': [
                    self._tenant_to_dict(t) for t in self._tenants.values()
                ]
            }
            
            with open(path, 'w') as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to save tenants: {e}")
    
    def _dict_to_tenant(self, data: Dict) -> Tenant:
        """字典转租户对象"""
        quota_data = data.get('quota', {})
        quota = TenantQuota(**quota_data)
        
        return Tenant(
            id=data['id'],
            name=data['name'],
            api_key=data['api_key'],
            quota=quota,
            config=data.get('config', {}),
            created_at=datetime.fromisoformat(data['created_at']) if 'created_at' in data else datetime.now(),
            is_active=data.get('is_active', True),
            metadata=data.get('metadata', {})
        )
    
    def _tenant_to_dict(self, tenant: Tenant) -> Dict:
        """租户对象转字典"""
        return {
            'id': tenant.id,
            'name': tenant.name,
            'api_key': tenant.api_key,
            'quota': {
                'max_requests_per_minute': tenant.quota.max_requests_per_minute,
                'max_tokens_per_day': tenant.quota.max_tokens_per_day,
                'max_documents': tenant.quota.max_documents,
                'max_storage_mb': tenant.quota.max_storage_mb,
                'max_concurrent_queries': tenant.quota.max_concurrent_queries,
            },
            'config': tenant.config,
            'created_at': tenant.created_at.isoformat(),
            'is_active': tenant.is_active,
            'metadata': tenant.metadata
        }
    
    async def create_tenant(
        self,
        name: str,
        quota: Optional[TenantQuota] = None,
        config: Optional[Dict] = None
    ) -> Tenant:
        """创建租户"""
        async with self._lock:
            import uuid
            import secrets
            
            tenant_id = f"tenant_{uuid.uuid4().hex[:12]}"
            api_key = f"rag_{secrets.token_urlsafe(32)}"
            
            tenant = Tenant(
                id=tenant_id,
                name=name,
                api_key=api_key,
                quota=quota or TenantQuota(),
                config=config or {}
            )
            
            self._tenants[tenant_id] = tenant
            self._api_key_map[api_key] = tenant_id
            
            self._save_tenants()
            logger.info(f"Created tenant: {tenant_id}")
            
            return tenant
    
    async def get_tenant(self, tenant_id: str) -> Optional[Tenant]:
        """获取租户"""
        return self._tenants.get(tenant_id)
    
    async def get_tenant_by_api_key(self, api_key: str) -> Optional[Tenant]:
        """通过API Key获取租户"""
        tenant_id = self._api_key_map.get(api_key)
        if tenant_id:
            return await self.get_tenant(tenant_id)
        return None
    
    async def validate_api_key(self, api_key: str) -> bool:
        """验证API Key"""
        tenant = await self.get_tenant_by_api_key(api_key)
        return tenant is not None and tenant.is_active
    
    async def update_quota(self, tenant_id: str, quota: TenantQuota) -> bool:
        """更新配额"""
        async with self._lock:
            if tenant_id not in self._tenants:
                return False
            
            self._tenants[tenant_id].quota = quota
            self._save_tenants()
            return True
    
    async def deactivate_tenant(self, tenant_id: str) -> bool:
        """停用租户"""
        async with self._lock:
            if tenant_id not in self._tenants:
                return False
            
            self._tenants[tenant_id].is_active = False
            self._save_tenants()
            logger.info(f"Deactivated tenant: {tenant_id}")
            return True
    
    async def delete_tenant(self, tenant_id: str) -> bool:
        """删除租户"""
        async with self._lock:
            if tenant_id not in self._tenants:
                return False
            
            tenant = self._tenants[tenant_id]
            del self._api_key_map[tenant.api_key]
            del self._tenants[tenant_id]
            
            self._save_tenants()
            logger.info(f"Deleted tenant: {tenant_id}")
            return True
    
    async def check_rate_limit(self, tenant_id: str) -> bool:
        """检查速率限制"""
        tenant = await self.get_tenant(tenant_id)
        if not tenant:
            return False
        
        # 简化实现：记录每分钟请求数
        now = datetime.now()
        minute_key = now.strftime("%Y-%m-%d-%H-%M")
        
        if tenant_id not in self._usage_stats:
            self._usage_stats[tenant_id] = {}
        
        if minute_key not in self._usage_stats[tenant_id]:
            self._usage_stats[tenant_id][minute_key] = 0
        
        current = self._usage_stats[tenant_id][minute_key]
        
        if current >= tenant.quota.max_requests_per_minute:
            logger.warning(f"Rate limit exceeded for tenant {tenant_id}")
            return False
        
        self._usage_stats[tenant_id][minute_key] += 1
        return True
    
    async def get_usage_stats(self, tenant_id: str) -> Dict[str, Any]:
        """获取使用统计"""
        tenant = await self.get_tenant(tenant_id)
        if not tenant:
            return {}
        
        stats = self._usage_stats.get(tenant_id, {})
        total_requests = sum(stats.values())
        
        return {
            'tenant_id': tenant_id,
            'tenant_name': tenant.name,
            'total_requests': total_requests,
            'quota': {
                'max_requests_per_minute': tenant.quota.max_requests_per_minute,
                'max_documents': tenant.quota.max_documents,
            },
            'recent_usage': list(stats.items())[-10:]  # 最近10分钟
        }
    
    async def list_tenants(self) -> List[Tenant]:
        """列出所有租户"""
        return list(self._tenants.values())


# 全局实例
_tenant_manager: Optional[TenantManager] = None


async def get_tenant_manager() -> TenantManager:
    """获取全局租户管理器"""
    global _tenant_manager
    if _tenant_manager is None:
        _tenant_manager = TenantManager()
    return _tenant_manager
