"""
Audit Log - 审计日志
支持操作记录、合规性、安全追踪
"""
import asyncio
import json
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
import aiofiles
import hashlib

from src.core.logging import get_logger

logger = get_logger(__name__)


class AuditAction(Enum):
    """审计动作类型"""
    # 查询类
    QUERY = "query"
    SEARCH = "search"
    RETRIEVE = "retrieve"
    
    # 文档类
    DOCUMENT_CREATE = "document.create"
    DOCUMENT_UPDATE = "document.update"
    DOCUMENT_DELETE = "document.delete"
    DOCUMENT_INGEST = "document.ingest"
    
    # 用户类
    USER_LOGIN = "user.login"
    USER_LOGOUT = "user.logout"
    USER_CREATE = "user.create"
    USER_UPDATE = "user.update"
    USER_DELETE = "user.delete"
    
    # 系统类
    CONFIG_CHANGE = "config.change"
    MODEL_UPDATE = "model.update"
    SYSTEM_ERROR = "system.error"
    SECURITY_ALERT = "security.alert"


@dataclass
class AuditLogEntry:
    """审计日志条目"""
    id: str
    timestamp: datetime
    action: str
    user_id: Optional[str]
    tenant_id: Optional[str]
    resource_type: str
    resource_id: Optional[str]
    request_ip: Optional[str]
    user_agent: Optional[str]
    request_data: Dict[str, Any]
    response_data: Dict[str, Any]
    status: str  # success, failure, denied
    error_message: Optional[str]
    duration_ms: int
    trace_id: Optional[str]
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data


class AuditLogger:
    """
    审计日志记录器
    
    功能：
    1. 操作日志记录
    2. 结构化输出
    3. 自动归档
    4. 合规性支持
    """
    
    def __init__(
        self,
        log_dir: str = "./data/audit",
        max_file_size: int = 100 * 1024 * 1024,  # 100MB
        retention_days: int = 365,
        batch_size: int = 100,
        flush_interval: int = 5
    ):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        self.max_file_size = max_file_size
        self.retention_days = retention_days
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        
        self._buffer: List[AuditLogEntry] = []
        self._lock = asyncio.Lock()
        self._flush_task: Optional[asyncio.Task] = None
        self._current_file: Optional[Path] = None
        
        # 启动自动刷新
        self._flush_task = asyncio.create_task(self._auto_flush())
        
        logger.info(f"Audit logger initialized: {log_dir}")
    
    def _generate_id(self) -> str:
        """生成日志ID"""
        timestamp = datetime.now().isoformat()
        random_suffix = hashlib.md5(
            f"{timestamp}{id(self)}".encode()
        ).hexdigest()[:8]
        return f"audit_{timestamp.replace(':', '-')}_{random_suffix}"
    
    async def log(
        self,
        action: AuditAction,
        resource_type: str,
        resource_id: Optional[str] = None,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        request_data: Optional[Dict] = None,
        response_data: Optional[Dict] = None,
        status: str = "success",
        error_message: Optional[str] = None,
        duration_ms: int = 0,
        request_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
        trace_id: Optional[str] = None
    ) -> AuditLogEntry:
        """
        记录审计日志
        
        Args:
            action: 动作类型
            resource_type: 资源类型
            resource_id: 资源ID
            user_id: 用户ID
            tenant_id: 租户ID
            request_data: 请求数据
            response_data: 响应数据
            status: 状态
            error_message: 错误信息
            duration_ms: 执行时长
            request_ip: 请求IP
            user_agent: 用户代理
            trace_id: 追踪ID
        """
        entry = AuditLogEntry(
            id=self._generate_id(),
            timestamp=datetime.now(),
            action=action.value,
            user_id=user_id,
            tenant_id=tenant_id,
            resource_type=resource_type,
            resource_id=resource_id,
            request_ip=request_ip,
            user_agent=user_agent,
            request_data=request_data or {},
            response_data=response_data or {},
            status=status,
            error_message=error_message,
            duration_ms=duration_ms,
            trace_id=trace_id
        )
        
        async with self._lock:
            self._buffer.append(entry)
            
            # 立即写入或批量写入
            if len(self._buffer) >= self.batch_size:
                await self._flush()
        
        # 同时输出到标准日志
        logger.info(
            f"Audit: {entry.action} | "
            f"user={entry.user_id} | "
            f"resource={entry.resource_type}:{entry.resource_id} | "
            f"status={entry.status}"
        )
        
        return entry
    
    async def _auto_flush(self):
        """自动刷新任务"""
        while True:
            try:
                await asyncio.sleep(self.flush_interval)
                async with self._lock:
                    if self._buffer:
                        await self._flush()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Audit auto-flush error: {e}")
    
    async def _flush(self):
        """刷新缓冲区到文件"""
        if not self._buffer:
            return
        
        try:
            # 获取当前日志文件
            log_file = self._get_current_file()
            
            # 写入日志条目
            lines = [json.dumps(entry.to_dict(), ensure_ascii=False) + "\n" 
                    for entry in self._buffer]
            
            async with aiofiles.open(log_file, 'a', encoding='utf-8') as f:
                await f.writelines(lines)
            
            logger.debug(f"Flushed {len(self._buffer)} audit entries to {log_file}")
            self._buffer.clear()
            
            # 检查文件大小并轮转
            await self._check_rotation(log_file)
            
        except Exception as e:
            logger.error(f"Failed to flush audit log: {e}")
    
    def _get_current_file(self) -> Path:
        """获取当前日志文件"""
        if self._current_file is None:
            date_str = datetime.now().strftime("%Y-%m-%d")
            self._current_file = self.log_dir / f"audit_{date_str}.log"
        return self._current_file
    
    async def _check_rotation(self, log_file: Path):
        """检查并执行日志轮转"""
        try:
            stat = log_file.stat()
            if stat.st_size > self.max_file_size:
                # 轮转文件
                timestamp = datetime.now().strftime("%H%M%S")
                new_name = log_file.stem + f"_{timestamp}.log"
                log_file.rename(log_file.parent / new_name)
                
                # 重置当前文件
                self._current_file = None
                
                logger.info(f"Rotated audit log: {new_name}")
        except Exception as e:
            logger.error(f"Log rotation failed: {e}")
    
    async def query(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100
    ) -> List[AuditLogEntry]:
        """查询审计日志"""
        results = []
        
        # 获取所有日志文件
        log_files = sorted(self.log_dir.glob("audit_*.log"))
        
        for log_file in log_files:
            try:
                async with aiofiles.open(log_file, 'r', encoding='utf-8') as f:
                    async for line in f:
                        try:
                            data = json.loads(line.strip())
                            
                            # 过滤条件
                            entry_time = datetime.fromisoformat(data['timestamp'])
                            
                            if start_time and entry_time < start_time:
                                continue
                            if end_time and entry_time > end_time:
                                continue
                            if user_id and data.get('user_id') != user_id:
                                continue
                            if tenant_id and data.get('tenant_id') != tenant_id:
                                continue
                            if action and data.get('action') != action:
                                continue
                            if resource_type and data.get('resource_type') != resource_type:
                                continue
                            if status and data.get('status') != status:
                                continue
                            
                            # 解析为AuditLogEntry
                            entry = AuditLogEntry(
                                id=data['id'],
                                timestamp=entry_time,
                                action=data['action'],
                                user_id=data.get('user_id'),
                                tenant_id=data.get('tenant_id'),
                                resource_type=data['resource_type'],
                                resource_id=data.get('resource_id'),
                                request_ip=data.get('request_ip'),
                                user_agent=data.get('user_agent'),
                                request_data=data.get('request_data', {}),
                                response_data=data.get('response_data', {}),
                                status=data['status'],
                                error_message=data.get('error_message'),
                                duration_ms=data.get('duration_ms', 0),
                                trace_id=data.get('trace_id')
                            )
                            
                            results.append(entry)
                            
                            if len(results) >= limit:
                                return results
                                
                        except json.JSONDecodeError:
                            continue
                            
            except Exception as e:
                logger.error(f"Failed to read audit log {log_file}: {e}")
        
        return results
    
    async def export(
        self,
        output_file: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        format: str = "json"
    ) -> int:
        """导出审计日志"""
        entries = await self.query(
            start_time=start_time,
            end_time=end_time,
            limit=10000
        )
        
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        if format == "json":
            async with aiofiles.open(output_path, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(
                    [entry.to_dict() for entry in entries],
                    ensure_ascii=False,
                    indent=2
                ))
        elif format == "jsonl":
            async with aiofiles.open(output_path, 'w', encoding='utf-8') as f:
                for entry in entries:
                    await f.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")
        
        logger.info(f"Exported {len(entries)} audit entries to {output_file}")
        return len(entries)
    
    async def close(self):
        """关闭审计日志记录器"""
        # 取消自动刷新任务
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
        
        # 刷新剩余日志
        async with self._lock:
            if self._buffer:
                await self._flush()
        
        logger.info("Audit logger closed")


# 全局实例
_audit_logger: Optional[AuditLogger] = None


async def get_audit_logger() -> AuditLogger:
    """获取全局审计日志记录器"""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger
