"""
技能执行器

负责任务规划、技能调用、结果校验、错误恢复
"""
import asyncio
import time
import json
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime

from .skill import Skill, SkillResult, SkillExecutionContext
from .skill_library import SkillLibrary


class SkillExecutor:
    """
    技能执行器
    
    核心能力：
    1. 任务规划（复杂任务拆解）
    2. 技能调用（同步/异步）
    3. 结果校验
    4. 错误恢复（重试、回退）
    5. 执行追踪
    """
    
    def __init__(
        self,
        skill_library: SkillLibrary,
        llm_client=None,
        memory_manager=None,
        max_retries: int = 3
    ):
        self.skill_library = skill_library
        self.llm_client = llm_client
        self.memory_manager = memory_manager
        self.max_retries = max_retries
        
        # 执行历史
        self.execution_history: List[Dict] = []
    
    async def execute_skill(
        self,
        skill_name: str,
        params: Dict[str, Any],
        context: SkillExecutionContext,
        auto_retry: bool = True
    ) -> SkillResult:
        """
        执行单个技能
        
        Args:
            skill_name: 技能名称
            params: 参数
            context: 执行上下文
            auto_retry: 失败是否自动重试
        
        Returns:
            SkillResult: 执行结果
        """
        skill = self.skill_library.get_skill(skill_name)
        if not skill:
            return SkillResult.error_result(f"技能不存在: {skill_name}")
        
        # 参数验证
        valid, error = skill.validate_params(params)
        if not valid:
            return SkillResult.error_result(f"参数验证失败: {error}")
        
        # 记录使用
        self.skill_library.record_usage(skill_name)
        
        # 执行（带重试）
        start_time = time.time()
        last_error = None
        
        for attempt in range(self.max_retries if auto_retry else 1):
            try:
                result = await skill.execute(params, context)
                execution_time = time.time() - start_time
                
                # 更新统计
                skill.update_stats(
                    success=result.success,
                    execution_time=execution_time
                )
                
                # 添加到执行链
                context.add_to_chain(skill_name, params, result)
                
                # 记录历史
                self._record_execution(
                    skill_name, params, result, execution_time
                )
                
                return result
                
            except Exception as e:
                last_error = str(e)
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(0.5 * (attempt + 1))  # 指数退避
                continue
        
        # 全部失败
        execution_time = time.time() - start_time
        result = SkillResult.error_result(
            f"执行失败（重试{self.max_retries}次）: {last_error}"
        )
        
        skill.update_stats(success=False, execution_time=execution_time)
        context.add_to_chain(skill_name, params, result)
        self._record_execution(skill_name, params, result, execution_time)
        
        return result
    
    async def execute_plan(
        self,
        plan: List[Dict[str, Any]],
        context: SkillExecutionContext,
        stop_on_error: bool = True
    ) -> List[SkillResult]:
        """
        执行计划（多步骤）
        
        Args:
            plan: 执行计划 [{"skill": "name", "params": {...}}, ...]
            context: 执行上下文
            stop_on_error: 出错是否停止
        
        Returns:
            List[SkillResult]: 各步骤结果
        """
        results = []
        accumulated_data = {}
        
        for step_idx, step in enumerate(plan):
            skill_name = step.get("skill")
            params = step.get("params", {})
            
            # 参数引用解析（$step_0.result 格式）
            resolved_params = self._resolve_params(params, accumulated_data)
            
            result = await self.execute_skill(
                skill_name, resolved_params, context
            )
            results.append(result)
            
            # 保存结果供后续步骤使用
            accumulated_data[f"step_{step_idx}"] = result.data
            
            if not result.success and stop_on_error:
                break
        
        return results
    
    def _resolve_params(
        self,
        params: Dict[str, Any],
        accumulated_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """解析参数引用"""
        resolved = {}
        
        for key, value in params.items():
            if isinstance(value, str) and value.startswith("$"):
                # 引用之前的结果
                ref_parts = value[1:].split(".")
                data = accumulated_data.get(ref_parts[0])
                
                # 处理嵌套引用
                for part in ref_parts[1:]:
                    if isinstance(data, dict):
                        data = data.get(part)
                    else:
                        data = None
                        break
                
                resolved[key] = data
            else:
                resolved[key] = value
        
        return resolved
    
    async def plan_and_execute(
        self,
        user_query: str,
        context: SkillExecutionContext
    ) -> Dict[str, Any]:
        """
        规划并执行任务
        
        基于用户查询自动规划执行步骤
        """
        # 1. 意图理解
        intent = await self._understand_intent(user_query)
        
        # 2. 技能选择
        relevant_skills = self.skill_library.recommend_skills(user_query)
        
        # 3. 生成执行计划
        plan = await self._generate_plan(
            user_query, intent, relevant_skills
        )
        
        # 4. 执行
        results = await self.execute_plan(plan, context)
        
        # 5. 汇总结果
        return {
            "intent": intent,
            "plan": plan,
            "results": [
                {
                    "skill": step.get("skill"),
                    "success": r.success,
                    "data": r.data,
                    "error": r.error
                }
                for step, r in zip(plan, results)
            ],
            "success": all(r.success for r in results)
        }
    
    async def _understand_intent(self, query: str) -> Dict[str, Any]:
        """理解用户意图"""
        # 简化实现：关键词匹配
        # 实际应该用LLM
        intent_types = {
            "search": ["查", "找", "搜索", "是多少"],
            "compare": ["对比", "比较", "区别", "差异"],
            "summarize": ["总结", "概括", "摘要", "简述"],
            "execute": ["执行", "运行", "生成", "创建"]
        }
        
        for intent_type, keywords in intent_types.items():
            for kw in keywords:
                if kw in query:
                    return {
                        "type": intent_type,
                        "confidence": 0.8
                    }
        
        return {"type": "unknown", "confidence": 0.5}
    
    async def _generate_plan(
        self,
        query: str,
        intent: Dict,
        skills: List[Skill]
    ) -> List[Dict[str, Any]]:
        """生成执行计划"""
        # 简化实现：基于意图选择
        plan = []
        
        if intent["type"] == "search":
            plan.append({
                "skill": "document_search",
                "params": {"query": query, "top_k": 5}
            })
        
        elif intent["type"] == "compare":
            # 拆解为多个搜索
            plan.extend([
                {"skill": "document_search", "params": {"query": query}},
                {"skill": "compare_documents", "params": {"docs": "$step_0.result"}}
            ])
        
        elif intent["type"] == "summarize":
            plan.extend([
                {"skill": "document_search", "params": {"query": query}},
                {"skill": "summarize", "params": {"content": "$step_0.result"}}
            ])
        
        # 默认兜底
        if not plan and skills:
            plan.append({
                "skill": skills[0].name,
                "params": {"query": query}
            })
        
        return plan
    
    def _record_execution(
        self,
        skill_name: str,
        params: Dict,
        result: SkillResult,
        execution_time: float
    ):
        """记录执行历史"""
        self.execution_history.append({
            "skill": skill_name,
            "params": params,
            "success": result.success,
            "execution_time": execution_time,
            "timestamp": datetime.now().isoformat()
        })
        
        # 限制历史大小
        if len(self.execution_history) > 1000:
            self.execution_history = self.execution_history[-500:]
    
    def get_execution_stats(self) -> Dict[str, Any]:
        """获取执行统计"""
        if not self.execution_history:
            return {}
        
        total = len(self.execution_history)
        success = sum(1 for h in self.execution_history if h["success"])
        
        return {
            "total_executions": total,
            "success_count": success,
            "success_rate": success / total if total > 0 else 0,
            "avg_execution_time": sum(
                h["execution_time"] for h in self.execution_history
            ) / total if total > 0 else 0
        }
