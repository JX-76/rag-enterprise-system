"""
RBAC - Role-Based Access Control
基于角色的权限控制
支持角色、权限、资源的多维控制
"""
import asyncio
from typing import Dict, List, Set, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
import json
import aiofiles

from src.core.logging import get_logger

logger = get_logger(__name__)


class Permission(Enum):
    """权限列表"""
    # 查询权限
    QUERY_READ = "query:read"
    QUERY_CREATE = "query:create"
    QUERY_DELETE = "query:delete"
    
    # 文档权限
    DOCUMENT_READ = "document:read"
    DOCUMENT_CREATE = "document:create"
    DOCUMENT_UPDATE = "document:update"
    DOCUMENT_DELETE = "document:delete"
    
    # 索引权限
    INDEX_READ = "index:read"
    INDEX_CREATE = "index:create"
    INDEX_UPDATE = "index:update"
    INDEX_DELETE = "index:delete"
    INDEX_REBUILD = "index:rebuild"
    
    # 用户权限
    USER_READ = "user:read"
    USER_CREATE = "user:create"
    USER_UPDATE = "user:update"
    USER_DELETE = "user:delete"
    
    # 系统权限
    SYSTEM_READ = "system:read"
    SYSTEM_CONFIG = "system:config"
    SYSTEM_ADMIN = "system:admin"
    
    # 模型权限
    MODEL_READ = "model:read"
    MODEL_UPDATE = "model:update"
    MODEL_SWITCH = "model:switch"


@dataclass
class Role:
    """角色"""
    id: str
    name: str
    description: str
    permissions: Set[str] = field(default_factory=set)
    parent_roles: List[str] = field(default_factory=list)
    is_system: bool = False
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class UserRoleAssignment:
    """用户角色分配"""
    user_id: str
    role_id: str
    tenant_id: Optional[str]
    assigned_by: str
    assigned_at: datetime
    expires_at: Optional[datetime] = None


class RBACManager:
    """
    RBAC权限管理器
    
    功能：
    1. 角色管理（CRUD）
    2. 权限分配
    3. 权限检查
    4. 角色继承
    5. 租户隔离
    """
    
    # 预定义角色
    DEFAULT_ROLES = {
        "admin": Role(
            id="admin",
            name="Administrator",
            description="Full system access",
            permissions={p.value for p in Permission},
            is_system=True
        ),
        "editor": Role(
            id="editor",
            name="Editor",
            description="Can manage documents and queries",
            permissions={
                Permission.QUERY_READ.value,
                Permission.QUERY_CREATE.value,
                Permission.DOCUMENT_READ.value,
                Permission.DOCUMENT_CREATE.value,
                Permission.DOCUMENT_UPDATE.value,
                Permission.DOCUMENT_DELETE.value,
                Permission.INDEX_READ.value,
            },
            is_system=True
        ),
        "viewer": Role(
            id="viewer",
            name="Viewer",
            description="Read-only access",
            permissions={
                Permission.QUERY_READ.value,
                Permission.DOCUMENT_READ.value,
                Permission.INDEX_READ.value,
            },
            is_system=True
        ),
        "api": Role(
            id="api",
            name="API User",
            description="API access only",
            permissions={
                Permission.QUERY_READ.value,
                Permission.QUERY_CREATE.value,
                Permission.DOCUMENT_READ.value,
            },
            is_system=True
        ),
    }
    
    def __init__(self, storage_path: str = "./data/rbac.json"):
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        
        self._roles: Dict[str, Role] = {}
        self._user_assignments: Dict[str, List[UserRoleAssignment]] = {}
        self._lock = asyncio.Lock()
        
        # 初始化默认角色
        self._roles.update(self.DEFAULT_ROLES)
        
        # 加载持久化数据
        self._load_data()
        
        logger.info(f"RBAC manager initialized with {len(self._roles)} roles")
    
    def _load_data(self):
        """加载数据"""
        if not self.storage_path.exists():
            return
        
        try:
            with open(self.storage_path, 'r') as f:
                data = json.load(f)
            
            # 加载自定义角色
            for role_data in data.get('roles', []):
                if role_data['id'] not in self.DEFAULT_ROLES:
                    self._roles[role_data['id']] = Role(
                        id=role_data['id'],
                        name=role_data['name'],
                        description=role_data['description'],
                        permissions=set(role_data['permissions']),
                        parent_roles=role_data.get('parent_roles', []),
                        is_system=role_data.get('is_system', False),
                        created_at=datetime.fromisoformat(role_data['created_at'])
                    )
            
            # 加载用户分配
            for user_id, assignments in data.get('assignments', {}).items():
                self._user_assignments[user_id] = [
                    UserRoleAssignment(
                        user_id=a['user_id'],
                        role_id=a['role_id'],
                        tenant_id=a.get('tenant_id'),
                        assigned_by=a['assigned_by'],
                        assigned_at=datetime.fromisoformat(a['assigned_at']),
                        expires_at=datetime.fromisoformat(a['expires_at']) if a.get('expires_at') else None
                    )
                    for a in assignments
                ]
            
            logger.info(f"Loaded {len(self._roles)} roles and {len(self._user_assignments)} user assignments")
            
        except Exception as e:
            logger.error(f"Failed to load RBAC data: {e}")
    
    async def _save_data(self):
        """保存数据"""
        async with self._lock:
            data = {
                'roles': [
                    {
                        'id': role.id,
                        'name': role.name,
                        'description': role.description,
                        'permissions': list(role.permissions),
                        'parent_roles': role.parent_roles,
                        'is_system': role.is_system,
                        'created_at': role.created_at.isoformat()
                    }
                    for role in self._roles.values()
                    if not role.is_system or role.id not in self.DEFAULT_ROLES
                ],
                'assignments': {
                    user_id: [
                        {
                            'user_id': a.user_id,
                            'role_id': a.role_id,
                            'tenant_id': a.tenant_id,
                            'assigned_by': a.assigned_by,
                            'assigned_at': a.assigned_at.isoformat(),
                            'expires_at': a.expires_at.isoformat() if a.expires_at else None
                        }
                        for a in assignments
                    ]
                    for user_id, assignments in self._user_assignments.items()
                }
            }
            
            async with aiofiles.open(self.storage_path, 'w') as f:
                await f.write(json.dumps(data, indent=2))
    
    async def create_role(
        self,
        role_id: str,
        name: str,
        description: str,
        permissions: List[str],
        parent_roles: Optional[List[str]] = None
    ) -> Role:
        """创建角色"""
        async with self._lock:
            if role_id in self._roles:
                raise ValueError(f"Role already exists: {role_id}")
            
            # 验证父角色
            if parent_roles:
                for parent_id in parent_roles:
                    if parent_id not in self._roles:
                        raise ValueError(f"Parent role not found: {parent_id}")
            
            role = Role(
                id=role_id,
                name=name,
                description=description,
                permissions=set(permissions),
                parent_roles=parent_roles or [],
                is_system=False,
                created_at=datetime.now()
            )
            
            self._roles[role_id] = role
            await self._save_data()
            
            logger.info(f"Created role: {role_id}")
            return role
    
    async def update_role(
        self,
        role_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        permissions: Optional[List[str]] = None
    ) -> Role:
        """更新角色"""
        async with self._lock:
            if role_id not in self._roles:
                raise ValueError(f"Role not found: {role_id}")
            
            role = self._roles[role_id]
            
            # 系统角色只能更新部分字段
            if role.is_system:
                if permissions:
                    raise PermissionError("Cannot modify system role permissions")
            
            if name:
                role.name = name
            if description:
                role.description = description
            if permissions and not role.is_system:
                role.permissions = set(permissions)
            
            await self._save_data()
            logger.info(f"Updated role: {role_id}")
            return role
    
    async def delete_role(self, role_id: str) -> bool:
        """删除角色"""
        async with self._lock:
            if role_id not in self._roles:
                return False
            
            role = self._roles[role_id]
            if role.is_system:
                raise PermissionError("Cannot delete system roles")
            
            del self._roles[role_id]
            await self._save_data()
            
            logger.info(f"Deleted role: {role_id}")
            return True
    
    async def assign_role(
        self,
        user_id: str,
        role_id: str,
        assigned_by: str,
        tenant_id: Optional[str] = None,
        expires_at: Optional[datetime] = None
    ) -> UserRoleAssignment:
        """分配角色给用户"""
        async with self._lock:
            if role_id not in self._roles:
                raise ValueError(f"Role not found: {role_id}")
            
            assignment = UserRoleAssignment(
                user_id=user_id,
                role_id=role_id,
                tenant_id=tenant_id,
                assigned_by=assigned_by,
                assigned_at=datetime.now(),
                expires_at=expires_at
            )
            
            if user_id not in self._user_assignments:
                self._user_assignments[user_id] = []
            
            # 检查是否已分配
            existing = [
                a for a in self._user_assignments[user_id]
                if a.role_id == role_id and a.tenant_id == tenant_id
            ]
            if existing:
                # 更新过期时间
                existing[0].expires_at = expires_at
            else:
                self._user_assignments[user_id].append(assignment)
            
            await self._save_data()
            logger.info(f"Assigned role {role_id} to user {user_id}")
            return assignment
    
    async def revoke_role(
        self,
        user_id: str,
        role_id: str,
        tenant_id: Optional[str] = None
    ) -> bool:
        """撤销用户角色"""
        async with self._lock:
            if user_id not in self._user_assignments:
                return False
            
            assignments = self._user_assignments[user_id]
            original_len = len(assignments)
            
            self._user_assignments[user_id] = [
                a for a in assignments
                if not (a.role_id == role_id and a.tenant_id == tenant_id)
            ]
            
            if len(self._user_assignments[user_id]) < original_len:
                await self._save_data()
                logger.info(f"Revoked role {role_id} from user {user_id}")
                return True
            
            return False
    
    def _get_role_permissions(self, role_id: str, visited: Optional[Set[str]] = None) -> Set[str]:
        """获取角色的所有权限（包括继承）"""
        if visited is None:
            visited = set()
        
        if role_id in visited:
            return set()  # 防止循环继承
        
        visited.add(role_id)
        
        if role_id not in self._roles:
            return set()
        
        role = self._roles[role_id]
        permissions = set(role.permissions)
        
        # 继承父角色权限
        for parent_id in role.parent_roles:
            permissions.update(self._get_role_permissions(parent_id, visited))
        
        return permissions
    
    async def check_permission(
        self,
        user_id: str,
        permission: str,
        tenant_id: Optional[str] = None,
        resource_id: Optional[str] = None
    ) -> bool:
        """检查用户是否有指定权限"""
        # 获取用户所有权限
        user_permissions = await self.get_user_permissions(user_id, tenant_id)
        
        # 检查是否有权限
        if permission in user_permissions:
            return True
        
        # 检查通配符权限（如 document:*）
        parts = permission.split(':')
        if len(parts) == 2:
            wildcard = f"{parts[0]}:*"
            if wildcard in user_permissions:
                return True
        
        # 检查系统管理员权限
        if Permission.SYSTEM_ADMIN.value in user_permissions:
            return True
        
        return False
    
    async def get_user_permissions(
        self,
        user_id: str,
        tenant_id: Optional[str] = None
    ) -> Set[str]:
        """获取用户的所有权限"""
        if user_id not in self._user_assignments:
            return set()
        
        all_permissions = set()
        now = datetime.now()
        
        for assignment in self._user_assignments[user_id]:
            # 检查租户
            if tenant_id and assignment.tenant_id != tenant_id:
                continue
            
            # 检查过期
            if assignment.expires_at and assignment.expires_at < now:
                continue
            
            # 获取角色权限
            role_permissions = self._get_role_permissions(assignment.role_id)
            all_permissions.update(role_permissions)
        
        return all_permissions
    
    async def get_user_roles(
        self,
        user_id: str,
        tenant_id: Optional[str] = None
    ) -> List[Role]:
        """获取用户的所有角色"""
        if user_id not in self._user_assignments:
            return []
        
        roles = []
        now = datetime.now()
        
        for assignment in self._user_assignments[user_id]:
            if tenant_id and assignment.tenant_id != tenant_id:
                continue
            
            if assignment.expires_at and assignment.expires_at < now:
                continue
            
            if assignment.role_id in self._roles:
                roles.append(self._roles[assignment.role_id])
        
        return roles
    
    def list_roles(self) -> List[Role]:
        """列出所有角色"""
        return list(self._roles.values())
    
    def get_role(self, role_id: str) -> Optional[Role]:
        """获取角色"""
        return self._roles.get(role_id)


# 全局实例
_rbac_manager: Optional[RBACManager] = None


def get_rbac_manager() -> RBACManager:
    """获取全局RBAC管理器"""
    global _rbac_manager
    if _rbac_manager is None:
        _rbac_manager = RBACManager()
    return _rbac_manager


# 便捷函数
async def require_permission(
    user_id: str,
    permission: str,
    tenant_id: Optional[str] = None
):
    """权限检查装饰器"""
    rbac = get_rbac_manager()
    if not await rbac.check_permission(user_id, permission, tenant_id):
        raise PermissionError(f"Permission denied: {permission}")
