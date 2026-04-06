"""
RAG Agent 主类

整合四层记忆 + 技能库 + 对话管理
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, AsyncIterator
import asyncio
import json

from ..memory import MemoryManager
from .skills import (
    SkillLibrary, SkillExecutor, SkillExecutionContext,
    get_builtin_skills
)
from .dialogue import DialogueManager


@dataclass
class AgentConfig:
    """Agent配置"""
    # 记忆配置
    enable_ultra_short: bool = True
    enable_short: bool = True
    enable_long: bool = True
    enable_global: bool = True
    
    # 技能配置
    max_skills_per_turn: int = 3
    auto_skill_selection: bool = True
    
    # 生成配置
    temperature: float = 0.7
    max_tokens: int = 2000
    
    # 安全配置
    require_confirmation_for: List[str] = field(
        default_factory=lambda: ["database_query", "generate_report"]
    )


class RAGAgent:
    """
    RAG Agent
    
    企业级Agent实现：
    - 四层记忆体系
    - 可扩展技能库
    - 任务规划与执行
    - 对话状态管理
    """
    
    def __init__(
        self,
        memory_manager: MemoryManager,
        skill_library: Optional[SkillLibrary] = None,
        llm_client=None,
        config: AgentConfig = None
    ):
        self.memory_manager = memory_manager
        self.skill_library = skill_library or SkillLibrary()
        self.llm_client = llm_client
        self.config = config or AgentConfig()
        
        # 执行器
        self.skill_executor = SkillExecutor(
            skill_library=self.skill_library,
            llm_client=llm_client,
            memory_manager=memory_manager
        )
        
        # 对话管理
        self.dialogue_manager = DialogueManager()
        
        # 注册内置技能
        self._register_builtin_skills()
    
    def _register_builtin_skills(self):
        """注册内置技能"""
        for skill in get_builtin_skills():
            self.skill_library.register(skill)
    
    async def chat(
        self,
        user_id: str,
        session_id: str,
        message: str,
        stream: bool = False
    ) -> Dict[str, Any]:
        """
        对话入口
        
        Args:
            user_id: 用户ID
            session_id: 会话ID
            message: 用户消息
            stream: 是否流式返回
        
        Returns:
            响应结果
        """
        # 1. 更新对话状态
        self.dialogue_manager.add_message(
            session_id, "user", message
        )
        
        # 2. 更新超短期记忆
        if self.config.enable_ultra_short:
            self.memory_manager.add_to_session_context(
                user_id, session_id, "user", message
            )
        
        # 3. 构建记忆上下文
        memory_context = ""
        if any([
            self.config.enable_ultra_short,
            self.config.enable_short,
            self.config.enable_long,
            self.config.enable_global
        ]):
            memory_context = self.memory_manager.build_memory_context(
                user_id, session_id, message
            )
        
        # 4. 意图理解与技能选择
        intent, skills = await self._understand_and_plan(
            message, memory_context
        )
        
        # 5. 执行技能
        context = SkillExecutionContext(
            user_id=user_id,
            session_id=session_id,
            memory_manager=self.memory_manager,
            llm_client=self.llm_client
        )
        
        skill_results = []
        if skills and self.config.auto_skill_selection:
            for skill_name in skills[:self.config.max_skills_per_turn]:
                result = await self.skill_executor.execute_skill(
                    skill_name,
                    {"query": message},
                    context
                )
                skill_results.append({
                    "skill": skill_name,
                    "success": result.success,
                    "data": result.data
                })
        
        # 6. 生成回复
        response = await self._generate_response(
            message=message,
            memory_context=memory_context,
            skill_results=skill_results,
            dialogue_history=self.dialogue_manager.get_history(session_id)
        )
        
        # 7. 更新记忆
        if self.config.enable_ultra_short:
            self.memory_manager.add_to_session_context(
                user_id, session_id, "assistant", response
            )
        
        self.dialogue_manager.add_message(
            session_id, "assistant", response
        )
        
        return {
            "response": response,
            "intent": intent,
            "skills_used": skills,
            "skill_results": skill_results,
            "memory_context_length": len(memory_context)
        }
    
    async def _understand_and_plan(
        self,
        message: str,
        memory_context: str
    ) -> tuple[Dict, List[str]]:
        """理解意图并规划技能"""
        # 简化实现：关键词 + 技能推荐
        # 实际应该用LLM做意图分类
        
        # 1. 技能推荐
        recommended = self.skill_library.recommend_skills(message, top_k=3)
        skill_names = [s.name for s in recommended]
        
        # 2. 简单意图识别
        intent = {"type": "chat", "confidence": 0.8}
        
        if any(kw in message for kw in ["搜索", "查找", "查"]):
            intent = {"type": "search", "confidence": 0.9}
            if "document_search" not in skill_names:
                skill_names.insert(0, "document_search")
        
        elif any(kw in message for kw in ["总结", "概括"]):
            intent = {"type": "summarize", "confidence": 0.85}
            if "summarize" not in skill_names:
                skill_names.insert(0, "summarize")
        
        elif any(kw in message for kw in ["对比", "比较"]):
            intent = {"type": "compare", "confidence": 0.85}
            if "compare_documents" not in skill_names:
                skill_names.insert(0, "compare_documents")
        
        elif any(kw in message for kw in ["报告", "生成"]):
            intent = {"type": "generate", "confidence": 0.8}
            if "generate_report" not in skill_names:
                skill_names.insert(0, "generate_report")
        
        return intent, skill_names
    
    async def _generate_response(
        self,
        message: str,
        memory_context: str,
        skill_results: List[Dict],
        dialogue_history: List[Dict]
    ) -> str:
        """生成回复"""
        # 构建Prompt
        prompt_parts = []
        
        # 系统提示
        prompt_parts.append("""你是一个企业级AI助手，基于RAG技术提供准确回答。
请根据提供的上下文和工具结果回答问题。如果无法从上下文中找到答案，请明确说明。""")
        
        # 记忆上下文
        if memory_context:
            prompt_parts.append(f"\n=== 记忆上下文 ===\n{memory_context}\n")
        
        # 对话历史
        if dialogue_history:
            prompt_parts.append("\n=== 对话历史 ===")
            for msg in dialogue_history[-5:]:  # 最近5条
                role = "用户" if msg["role"] == "user" else "助手"
                prompt_parts.append(f"{role}: {msg['content']}")
            prompt_parts.append("")
        
        # 技能执行结果
        if skill_results:
            prompt_parts.append("\n=== 工具执行结果 ===")
            for result in skill_results:
                status = "✓" if result["success"] else "✗"
                prompt_parts.append(f"[{status}] {result['skill']}: {result['data']}")
            prompt_parts.append("")
        
        # 当前问题
        prompt_parts.append(f"\n用户问题: {message}\n")
        prompt_parts.append("请回答:")
        
        full_prompt = "\n".join(prompt_parts)
        
        # 调用LLM生成
        if self.llm_client:
            try:
                # TODO: 实际LLM调用
                # response = await self.llm_client.generate(full_prompt)
                return f"[基于记忆和工具结果回答] {message}"
            except Exception as e:
                return f"生成回复时出错: {str(e)}"
        
        # 无LLM时的兜底回复
        return f"[系统提示: 已调用技能{len(skill_results)}个] 您的问题是: {message}"
    
    async def execute_task(
        self,
        user_id: str,
        session_id: str,
        task_description: str
    ) -> Dict[str, Any]:
        """
        执行复杂任务
        
        自动规划并执行多步骤任务
        """
        context = SkillExecutionContext(
            user_id=user_id,
            session_id=session_id,
            memory_manager=self.memory_manager,
            llm_client=self.llm_client
        )
        
        result = await self.skill_executor.plan_and_execute(
            task_description, context
        )
        
        return result
    
    def get_agent_status(self) -> Dict[str, Any]:
        """获取Agent状态"""
        return {
            "skill_count": len(self.skill_library),
            "skills": [
                s.to_dict()
                for s in self.skill_library.list_skills()
            ],
            "execution_stats": self.skill_executor.get_execution_stats(),
            "popular_skills": self.skill_library.get_popular_skills(5)
        }
