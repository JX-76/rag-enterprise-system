"""
Connection Pool - 通用连接池管理
支持Redis、向量库等资源的连接复用
"""
import asyncio
from typing import Any, Optional, Dict, Callable, TypeVar
from dataclasses import dataclass
from datetime import datetime, timedelta
import threading

from src.core.logging import get_logger

logger = get_logger(__name__)

T = TypeVar('T')


@dataclass
class PooledConnection:
    """连接池中的连接"""
    connection: Any
    created_at: datetime
    last_used: datetime
    use_count: int = 0
    is_valid: bool = True


class ConnectionPool:
    """
    通用连接池
    
    特性：
    - 最大/最小连接数控制
    - 连接健康检查
    - 空闲超时清理
    - 等待队列
    """
    
    def __init__(
        self,
        name: str,
        factory: Callable[[], Any],
        min_connections: int = 2,
        max_connections: int = 10,
        max_idle_time: int = 300,  # 5分钟
        max_lifetime: int = 3600,  # 1小时
        health_check_interval: int = 30,
        connection_timeout: float = 5.0
    ):
        self.name = name
        self.factory = factory
        self.min_connections = min_connections
        self.max_connections = max_connections
        self.max_idle_time = timedelta(seconds=max_idle_time)
        self.max_lifetime = timedelta(seconds=max_lifetime)
        self.connection_timeout = connection_timeout
        
        self._pool: asyncio.Queue[PooledConnection] = asyncio.Queue()
        self._all_connections: Dict[Any, PooledConnection] = {}
        self._lock = asyncio.Lock()
        self._semaphore = asyncio.Semaphore(max_connections)
        self._closed = False
        self._health_check_task: Optional[asyncio.Task] = None
        
        logger.info(f"Initialized {name} connection pool (min={min_connections}, max={max_connections})")
    
    async def initialize(self):
        """初始化连接池"""
        # 创建最小连接数
        for _ in range(self.min_connections):
            try:
                conn = await self._create_connection()
                await self._pool.put(conn)
            except Exception as e:
                logger.error(f"Failed to create initial connection: {e}")
        
        # 启动健康检查
        self._health_check_task = asyncio.create_task(
            self._health_check_loop()
        )
        
        logger.info(f"{self.name} pool initialized with {self._pool.qsize()} connections")
    
    async def _create_connection(self) -> PooledConnection:
        """创建新连接"""
        try:
            if asyncio.iscoroutinefunction(self.factory):
                conn = await asyncio.wait_for(
                    self.factory(),
                    timeout=self.connection_timeout
                )
            else:
                conn = self.factory()
            
            now = datetime.now()
            pooled = PooledConnection(
                connection=conn,
                created_at=now,
                last_used=now,
                use_count=0,
                is_valid=True
            )
            
            async with self._lock:
                self._all_connections[conn] = pooled
            
            return pooled
            
        except asyncio.TimeoutError:
            raise Exception(f"Connection creation timed out after {self.connection_timeout}s")
        except Exception as e:
            raise Exception(f"Failed to create connection: {e}")
    
    async def acquire(self) -> Any:
        """获取连接"""
        if self._closed:
            raise Exception("Pool is closed")
        
        async with self._semaphore:
            # 尝试从池获取
            if not self._pool.empty():
                pooled = await self._pool.get()
                
                # 检查连接是否有效
                if await self._validate_connection(pooled):
                    pooled.last_used = datetime.now()
                    pooled.use_count += 1
                    return pooled.connection
                else:
                    # 无效连接，创建新的
                    await self._destroy_connection(pooled)
            
            # 创建新连接
            pooled = await self._create_connection()
            pooled.use_count += 1
            return pooled.connection
    
    async def release(self, connection: Any):
        """释放连接"""
        if self._closed:
            await self._destroy_connection(connection)
            return
        
        async with self._lock:
            pooled = self._all_connections.get(connection)
            if not pooled:
                return
            
            # 检查连接是否还有效
            if not await self._validate_connection(pooled):
                await self._destroy_connection(pooled)
                return
            
            pooled.last_used = datetime.now()
            
            # 归还到池中
            try:
                self._pool.put_nowait(pooled)
            except asyncio.QueueFull:
                await self._destroy_connection(pooled)
    
    async def _validate_connection(self, pooled: PooledConnection) -> bool:
        """验证连接有效性"""
        if not pooled.is_valid:
            return False
        
        # 检查生命周期
        age = datetime.now() - pooled.created_at
        if age > self.max_lifetime:
            return False
        
        # 尝试ping（如果连接支持）
        if hasattr(pooled.connection, 'ping'):
            try:
                if asyncio.iscoroutinefunction(pooled.connection.ping):
                    await pooled.connection.ping()
                else:
                    pooled.connection.ping()
                return True
            except Exception:
                return False
        
        return True
    
    async def _destroy_connection(self, pooled_or_conn: Any):
        """销毁连接"""
        if isinstance(pooled_or_conn, PooledConnection):
            pooled = pooled_or_conn
            conn = pooled.connection
        else:
            conn = pooled_or_conn
            async with self._lock:
                pooled = self._all_connections.get(conn)
        
        if pooled:
            pooled.is_valid = False
            
            async with self._lock:
                if conn in self._all_connections:
                    del self._all_connections[conn]
        
        # 调用连接的close方法
        try:
            if hasattr(conn, 'close'):
                if asyncio.iscoroutinefunction(conn.close):
                    await conn.close()
                else:
                    conn.close()
            elif hasattr(conn, 'disconnect'):
                if asyncio.iscoroutinefunction(conn.disconnect):
                    await conn.disconnect()
                else:
                    conn.disconnect()
        except Exception as e:
            logger.debug(f"Error closing connection: {e}")
    
    async def _health_check_loop(self):
        """健康检查循环"""
        while not self._closed:
            try:
                await asyncio.sleep(30)  # 30秒检查一次
                
                if self._closed:
                    break
                
                await self._cleanup_idle_connections()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check error: {e}")
    
    async def _cleanup_idle_connections(self):
        """清理空闲连接"""
        now = datetime.now()
        to_remove = []
        
        # 找出空闲超时的连接
        async with self._lock:
            for conn, pooled in list(self._all_connections.items()):
                idle_time = now - pooled.last_used
                if idle_time > self.max_idle_time and pooled.use_count > 0:
                    to_remove.append(pooled)
        
        # 销毁过期连接
        for pooled in to_remove:
            await self._destroy_connection(pooled)
            logger.debug(f"Destroyed idle connection from {self.name} pool")
    
    async def close(self):
        """关闭连接池"""
        self._closed = True
        
        # 取消健康检查
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
        
        # 关闭所有连接
        async with self._lock:
            for pooled in list(self._all_connections.values()):
                await self._destroy_connection(pooled)
            
            self._all_connections.clear()
        
        # 清空队列
        while not self._pool.empty():
            try:
                pooled = self._pool.get_nowait()
                await self._destroy_connection(pooled)
            except asyncio.QueueEmpty:
                break
        
        logger.info(f"{self.name} pool closed")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取池状态"""
        return {
            'name': self.name,
            'available': self._pool.qsize(),
            'total': len(self._all_connections),
            'max': self.max_connections,
            'closed': self._closed
        }


class PooledConnectionContext:
    """连接池上下文管理器"""
    
    def __init__(self, pool: ConnectionPool):
        self.pool = pool
        self.connection: Optional[Any] = None
    
    async def __aenter__(self):
        self.connection = await self.pool.acquire()
        return self.connection
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.connection:
            await self.pool.release(self.connection)


# 预定义的连接池管理器
_connection_pools: Dict[str, ConnectionPool] = {}


async def get_connection_pool(
    name: str,
    factory: Optional[Callable] = None,
    **kwargs
) -> ConnectionPool:
    """获取或创建连接池"""
    global _connection_pools
    
    if name not in _connection_pools:
        if factory is None:
            raise ValueError(f"Factory required for new pool: {name}")
        
        pool = ConnectionPool(name=name, factory=factory, **kwargs)
        await pool.initialize()
        _connection_pools[name] = pool
    
    return _connection_pools[name]


async def close_all_pools():
    """关闭所有连接池"""
    global _connection_pools
    
    for pool in _connection_pools.values():
        await pool.close()
    
    _connection_pools.clear()
