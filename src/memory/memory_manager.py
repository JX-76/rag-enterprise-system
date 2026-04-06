"""
Memory 四层架构管理器

核心能力：
1. 四层记忆存储和检索
2. 记忆更新策略（RL优化基础）
3. 遗忘机制（基于访问频率和时间）
4. 记忆融合和冲突解决
"""
import hashlib
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from collections import defaultdict

from .memory_types import (
    Memory, MemoryLayer,
    UltraShortTermMemory, ShortTermMemory,
    LongTermMemory, GlobalMemory
)


class MemoryManager:
    """
    记忆管理器
    
    管理四层记忆：
    - 超短期：内存存储（当前会话）
    - 短期：Redis（近7天）
    - 长期：PostgreSQL（用户画像）
    - 全局：向量数据库（企业知识）
    """
    
    def __init__(
        self,
        redis_client=None,
        pg_conn=None,
        vector_store=None
    ):
        self.redis = redis_client
        self.pg_conn = pg_conn
        self.vector_store = vector_store
        
        # 超短期记忆：内存存储
        self.ultra_short_memory: Dict[str, UltraShortTermMemory] = {}
        
        # 短期记忆TTL（7天）
        self.short_term_ttl = 7 * 24 * 3600  # 7天秒数
        
        # 遗忘策略阈值
        self.forgotten_threshold = 30  # 30天未访问
        self.importance_decay = 0.95  # 重要性衰减系数
    
    # ========== 超短期记忆 ==========
    
    def get_or_create_ultra_short(
        self,
        user_id: str,
        session_id: str,
        context_window: int = 10
    ) -> UltraShortTermMemory:
        """获取或创建超短期记忆"""
        key = f"{user_id}:{session_id}"
        if key not in self.ultra_short_memory:
            self.ultra_short_memory[key] = UltraShortTermMemory(
                id=key,
                user_id=user_id,
                session_id=session_id,
                layer=MemoryLayer.ULTRA_SHORT,
                content="",
                context_window=context_window
            )
        return self.ultra_short_memory[key]
    
    def add_to_session_context(
        self,
        user_id: str,
        session_id: str,
        role: str,
        content: str,
        metadata: dict = None
    ):
        """添加消息到当前会话上下文"""
        memory = self.get_or_create_ultra_short(user_id, session_id)
        memory.add_message(role, content, metadata)
        memory.access_count += 1
        return memory
    
    def get_session_context(
        self,
        user_id: str,
        session_id: str
    ) -> Optional[str]:
        """获取当前会话上下文"""
        key = f"{user_id}:{session_id}"
        if key in self.ultra_short_memory:
            memory = self.ultra_short_memory[key]
            memory.access_count += 1
            return memory.get_context()
        return None
    
    def clear_session_context(self, user_id: str, session_id: str):
        """清理会话上下文"""
        key = f"{user_id}:{session_id}"
        if key in self.ultra_short_memory:
            del self.ultra_short_memory[key]
    
    # ========== 短期记忆 ==========
    
    def save_short_term(self, memory: ShortTermMemory):
        """保存短期记忆到Redis"""
        if not self.redis:
            return
        
        key = f"memory:short:{memory.user_id}"
        data = json.dumps(memory.to_dict())
        
        # 使用Redis Hash存储，按时间过期
        self.redis.hset(key, memory.id, data)
        self.redis.expire(key, self.short_term_ttl)
    
    def get_short_term(
        self,
        user_id: str,
        limit: int = 10
    ) -> List[ShortTermMemory]:
        """获取用户短期记忆"""
        if not self.redis:
            return []
        
        key = f"memory:short:{user_id}"
        memories = []
        
        # 获取最近7天的记忆
        all_data = self.redis.hgetall(key)
        for data in all_data.values():
            try:
                memory = ShortTermMemory.from_dict(json.loads(data))
                # 只返回7天内的
                if datetime.now() - memory.created_at < timedelta(days=7):
                    memory.access_count += 1
                    memories.append(memory)
            except:
                continue
        
        # 按时间倒序
        memories.sort(key=lambda x: x.updated_at, reverse=True)
        return memories[:limit]
    
    def add_session_summary(
        self,
        user_id: str,
        session_id: str,
        summary: str,
        key_entities: List[str]
    ):
        """添加会话摘要到短期记忆"""
        memory = ShortTermMemory(
            id=f"{user_id}:{session_id}:summary",
            user_id=user_id,
            session_id=session_id,
            layer=MemoryLayer.SHORT,
            content=summary,
            session_summary=summary,
            key_entities=key_entities
        )
        self.save_short_term(memory)
        return memory
    
    # ========== 长期记忆 ==========
    
    def save_long_term(self, memory: LongTermMemory):
        """保存长期记忆到PostgreSQL"""
        if not self.pg_conn:
            return
        
        cursor = self.pg_conn.cursor()
        cursor.execute("""
            INSERT INTO long_term_memory (
                id, user_id, content, user_profile, preferences,
                frequent_topics, knowledge_gaps, embedding,
                created_at, updated_at, access_count, importance_score
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                content = EXCLUDED.content,
                user_profile = EXCLUDED.user_profile,
                preferences = EXCLUDED.preferences,
                frequent_topics = EXCLUDED.frequent_topics,
                updated_at = EXCLUDED.updated_at,
                access_count = EXCLUDED.access_count
        """, (
            memory.id, memory.user_id, memory.content,
            json.dumps(memory.user_profile),
            json.dumps(memory.preferences),
            json.dumps(memory.frequent_topics),
            json.dumps(memory.knowledge_gaps),
            memory.embedding,
            memory.created_at, memory.updated_at,
            memory.access_count, memory.importance_score
        ))
        self.pg_conn.commit()
    
    def get_long_term(self, user_id: str) -> Optional[LongTermMemory]:
        """获取用户长期记忆（用户画像）"""
        if not self.pg_conn:
            return None
        
        cursor = self.pg_conn.cursor()
        cursor.execute(
            "SELECT * FROM long_term_memory WHERE user_id = %s",
            (user_id,)
        )
        row = cursor.fetchone()
        
        if row:
            memory = LongTermMemory(
                id=row[0],
                user_id=row[1],
                layer=MemoryLayer.LONG,
                content=row[2],
                user_profile=json.loads(row[3]),
                preferences=json.loads(row[4]),
                frequent_topics=json.loads(row[5]),
                knowledge_gaps=json.loads(row[6]),
                embedding=row[7],
                created_at=row[8],
                updated_at=row[9],
                access_count=row[10],
                importance_score=row[11]
            )
            memory.access_count += 1
            return memory
        
        # 没有则创建新的
        return LongTermMemory(
            id=f"{user_id}:profile",
            user_id=user_id,
            layer=MemoryLayer.LONG,
            content=""
        )
    
    def update_user_preference(
        self,
        user_id: str,
        key: str,
        value: Any
    ):
        """更新用户偏好"""
        memory = self.get_long_term(user_id)
        if memory:
            memory.update_preference(key, value)
            memory.updated_at = datetime.now()
            self.save_long_term(memory)
    
    # ========== 全局记忆 ==========
    
    def save_global(self, memory: GlobalMemory):
        """保存全局记忆到向量数据库"""
        if not self.vector_store:
            return
        
        # 向量化内容
        # TODO: 接入embedding service
        # embedding = self.embedding_service.encode(memory.content)
        # memory.embedding = embedding
        
        # 存储到向量库
        self.vector_store.add_documents([{
            "id": memory.id,
            "content": memory.content,
            "metadata": {
                "category": memory.category,
                "source": memory.source,
                "tags": memory.tags,
                "approved": memory.approved,
                "version": memory.version
            }
        }], [memory.embedding] if memory.embedding else None)
    
    def search_global(
        self,
        query: str,
        top_k: int = 5,
        filters: dict = None
    ) -> List[GlobalMemory]:
        """检索全局记忆"""
        if not self.vector_store:
            return []
        
        # TODO: 向量化查询并检索
        # query_embedding = self.embedding_service.encode(query)
        # results = self.vector_store.search(query_embedding, top_k)
        
        return []
    
    # ========== 记忆检索（融合） ==========
    
    def retrieve_relevant_memories(
        self,
        user_id: str,
        session_id: str,
        query: str,
        top_k: int = 10
    ) -> Dict[MemoryLayer, List[Memory]]:
        """
        检索相关记忆
        
        策略：
        1. 超短期：必取（当前会话上下文）
        2. 短期：最近7天相关会话
        3. 长期：用户画像和偏好
        4. 全局：企业知识库语义检索
        """
        results = defaultdict(list)
        
        # 1. 超短期记忆（当前会话）- 返回UltraShortTermMemory对象
        key = f"{user_id}:{session_id}"
        if key in self.ultra_short_memory:
            ultra_short = self.ultra_short_memory[key]
            ultra_short.access_count += 1
            results[MemoryLayer.ULTRA_SHORT] = [ultra_short]
        
        # 2. 短期记忆（近7天）
        short_term = self.get_short_term(user_id, limit=5)
        results[MemoryLayer.SHORT] = short_term
        
        # 3. 长期记忆（用户画像）
        long_term = self.get_long_term(user_id)
        if long_term:
            results[MemoryLayer.LONG] = [long_term]
        
        # 4. 全局记忆（语义检索）
        global_memories = self.search_global(query, top_k=top_k)
        results[MemoryLayer.GLOBAL] = global_memories
        
        return dict(results)
    
    def build_memory_context(
        self,
        user_id: str,
        session_id: str,
        query: str
    ) -> str:
        """
        构建记忆上下文
        
        按优先级融合四层记忆
        """
        memories = self.retrieve_relevant_memories(user_id, session_id, query)
        
        context_parts = []
        
        # 1. 超短期（当前会话）- 最高优先级
        if MemoryLayer.ULTRA_SHORT in memories:
            ultra_short = memories[MemoryLayer.ULTRA_SHORT][0]
            if isinstance(ultra_short, UltraShortTermMemory):
                context = ultra_short.get_context()
                if context:
                    context_parts.append("=== 当前会话 ===")
                    context_parts.append(context)
        
        # 2. 长期（用户画像）
        if MemoryLayer.LONG in memories:
            profile = memories[MemoryLayer.LONG][0]
            if profile.preferences or profile.frequent_topics:
                context_parts.append("=== 用户偏好 ===")
                if profile.domain_expertise:
                    context_parts.append(f"专业领域: {profile.domain_expertise}")
                if profile.response_style:
                    context_parts.append(f"回答风格: {profile.response_style}")
                if profile.frequent_topics:
                    context_parts.append(f"关注话题: {', '.join(profile.frequent_topics[:5])}")
        
        # 3. 短期（相关历史）
        if MemoryLayer.SHORT in memories:
            short_memories = memories[MemoryLayer.SHORT]
            if short_memories:
                context_parts.append("=== 相关历史 ===")
                for mem in short_memories[:3]:
                    if hasattr(mem, 'session_summary'):
                        context_parts.append(f"- {mem.session_summary}")
        
        # 4. 全局知识
        if MemoryLayer.GLOBAL in memories:
            global_mems = memories[MemoryLayer.GLOBAL]
            if global_mems:
                context_parts.append("=== 企业知识 ===")
                for mem in global_mems[:3]:
                    context_parts.append(f"- {mem.content[:200]}...")
        
        return "\n\n".join(context_parts)
    
    # ========== 记忆更新策略（RL基础） ==========
    
    def update_memory_importance(
        self,
        memory: Memory,
        feedback: float  # -1到1的反馈
    ):
        """
        更新记忆重要性（RL优化基础）
        
        feedback > 0: 记忆有用，增加重要性
        feedback < 0: 记忆无用或有害，降低重要性
        """
        # 简单线性更新
        memory.importance_score += feedback * 0.1
        memory.importance_score = max(0, min(memory.importance_score, 2))
        memory.updated_at = datetime.now()
    
    def apply_forgetting(self):
        """
        应用遗忘机制
        
        策略：
        1. 时间衰减：长期未访问的记忆重要性下降
        2. 重要性阈值：低于阈值的记忆标记为遗忘
        3. 定期清理：物理删除遗忘记忆
        """
        if not self.pg_conn:
            return
        
        cursor = self.pg_conn.cursor()
        
        # 时间衰减
        cursor.execute("""
            UPDATE long_term_memory
            SET importance_score = importance_score * %s,
                updated_at = NOW()
            WHERE updated_at < NOW() - INTERVAL '7 days'
        """, (self.importance_decay,))
        
        # 标记遗忘（30天未访问且重要性低）
        cursor.execute("""
            UPDATE long_term_memory
            SET metadata = metadata || '{"forgotten": true}'
            WHERE updated_at < NOW() - INTERVAL '30 days'
              AND importance_score < 0.3
        """)
        
        self.pg_conn.commit()
    
    def consolidate_session_to_long_term(
        self,
        user_id: str,
        session_id: str
    ):
        """
        会话结束后，将重要信息固化到长期记忆
        
        策略：
        1. 提取高频话题
        2. 更新用户偏好
        3. 识别知识盲区
        """
        # 获取会话超短期记忆
        key = f"{user_id}:{session_id}"
        if key not in self.ultra_short_memory:
            return
        
        session_memory = self.ultra_short_memory[key]
        
        # 提取高频话题（简单实现：统计关键词）
        # TODO: 接入LLM做会话总结
        
        # 更新长期记忆
        long_term = self.get_long_term(user_id)
        
        # 如果会话很长，提取话题
        if len(session_memory.messages) > 5:
            # 简单提取：取用户问得最多的主题词
            # 实际应该用LLM总结
            pass
        
        self.save_long_term(long_term)
        
        # 生成会话摘要存入短期记忆
        # TODO: 用LLM生成摘要
        summary = f"会话共{len(session_memory.messages)}条消息"
        self.add_session_summary(user_id, session_id, summary, [])
