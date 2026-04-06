"""
技能定义基类
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Callable
from enum import Enum
import json


class ParameterType(Enum):
    """参数类型"""
    STRING = "string"
    INTEGER = "integer"
    NUMBER = "number"
    BOOLEAN = "boolean"
    ARRAY = "array"
    OBJECT = "object"


@dataclass
class SkillParameter:
    """技能参数定义"""
    name: str
    description: str
    type: ParameterType
    required: bool = True
    default: Any = None
    enum: Optional[List[Any]] = None  # 枚举值
    examples: List[Any] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "type": self.type.value,
            "required": self.required,
            "default": self.default,
            "enum": self.enum,
            "examples": self.examples
        }
    
    def validate(self, value: Any) -> tuple[bool, str]:
        """验证参数值"""
        if value is None:
            if self.required and self.default is None:
                return False, f"参数 {self.name} 必填"
            return True, ""
        
        # 类型检查
        if self.type == ParameterType.STRING and not isinstance(value, str):
            return False, f"参数 {self.name} 应为字符串"
        elif self.type == ParameterType.INTEGER and not isinstance(value, int):
            return False, f"参数 {self.name} 应为整数"
        elif self.type == ParameterType.NUMBER and not isinstance(value, (int, float)):
            return False, f"参数 {self.name} 应为数字"
        elif self.type == ParameterType.BOOLEAN and not isinstance(value, bool):
            return False, f"参数 {self.name} 应为布尔值"
        
        # 枚举检查
        if self.enum and value not in self.enum:
            return False, f"参数 {self.name} 值 {value} 不在允许范围内"
        
        return True, ""


@dataclass
class SkillResult:
    """技能执行结果"""
    success: bool
    data: Any = None
    error: Optional[str] = None
    execution_time: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def success_result(cls, data: Any, **kwargs) -> 'SkillResult':
        return cls(success=True, data=data, **kwargs)
    
    @classmethod
    def error_result(cls, error: str, **kwargs) -> 'SkillResult':
        return cls(success=False, error=error, **kwargs)


@dataclass
class SkillExecutionContext:
    """技能执行上下文"""
    user_id: str
    session_id: str
    memory_manager: Any = None
    llm_client: Any = None
    tool_registry: Dict[str, Any] = field(default_factory=dict)
    
    # 执行链追踪
    execution_chain: List[Dict] = field(default_factory=list)
    
    def add_to_chain(self, skill_name: str, params: dict, result: SkillResult):
        """记录执行步骤"""
        self.execution_chain.append({
            "skill": skill_name,
            "params": params,
            "success": result.success,
            "timestamp": datetime.now().isoformat()
        })


class Skill(ABC):
    """
    技能基类
    
    所有具体技能继承此类
    """
    
    def __init__(
        self,
        name: str,
        description: str,
        parameters: List[SkillParameter],
        category: str = "general",
        tags: List[str] = None,
        requires_confirmation: bool = False
    ):
        self.name = name
        self.description = description
        self.parameters = {p.name: p for p in parameters}
        self.parameters_list = parameters
        self.category = category
        self.tags = tags or []
        self.requires_confirmation = requires_confirmation
        
        # 执行统计（用于RL优化）
        self.execution_count = 0
        self.success_count = 0
        self.total_execution_time = 0.0
        self.average_rating = 1.0  # 平均评分（-1到1）
    
    @abstractmethod
    async def execute(
        self,
        params: Dict[str, Any],
        context: SkillExecutionContext
    ) -> SkillResult:
        """
        执行技能
        
        Args:
            params: 参数字典
            context: 执行上下文
        
        Returns:
            SkillResult: 执行结果
        """
        pass
    
    def validate_params(self, params: Dict[str, Any]) -> tuple[bool, str]:
        """验证参数"""
        for name, param_def in self.parameters.items():
            value = params.get(name, param_def.default)
            valid, error = param_def.validate(value)
            if not valid:
                return False, error
        
        # 检查未定义的必填参数
        for name, param_def in self.parameters.items():
            if param_def.required and name not in params and param_def.default is None:
                return False, f"缺少必填参数: {name}"
        
        return True, ""
    
    def get_param_schema(self) -> dict:
        """获取参数Schema（OpenAI函数调用格式）"""
        properties = {}
        required = []
        
        for param in self.parameters_list:
            prop = {
                "type": param.type.value,
                "description": param.description
            }
            if param.enum:
                prop["enum"] = param.enum
            if param.examples:
                prop["examples"] = param.examples
            
            properties[param.name] = prop
            
            if param.required:
                required.append(param.name)
        
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required
                }
            }
        }
    
    def update_stats(self, success: bool, execution_time: float, rating: float = 0):
        """更新执行统计"""
        self.execution_count += 1
        if success:
            self.success_count += 1
        self.total_execution_time += execution_time
        
        # 更新平均评分（滑动平均）
        if rating != 0:
            self.average_rating = (self.average_rating * 0.9 + rating * 0.1)
    
    @property
    def success_rate(self) -> float:
        """成功率"""
        if self.execution_count == 0:
            return 1.0
        return self.success_count / self.execution_count
    
    @property
    def avg_execution_time(self) -> float:
        """平均执行时间"""
        if self.execution_count == 0:
            return 0.0
        return self.total_execution_time / self.execution_count
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "tags": self.tags,
            "parameters": [p.to_dict() for p in self.parameters_list],
            "requires_confirmation": self.requires_confirmation,
            "stats": {
                "execution_count": self.execution_count,
                "success_rate": self.success_rate,
                "avg_execution_time": self.avg_execution_time,
                "average_rating": self.average_rating
            }
        }


class CompositeSkill(Skill):
    """
    组合技能
    
    多个子技能按顺序执行
    """
    
    def __init__(
        self,
        name: str,
        description: str,
        sub_skills: List[tuple[str, Dict[str, str]]],  # [(skill_name, param_mapping)]
        **kwargs
    ):
        super().__init__(name, description, [], **kwargs)
        self.sub_skills = sub_skills  # 子技能及参数映射
        self.skill_library = None  # 需要外部注入
    
    async def execute(
        self,
        params: Dict[str, Any],
        context: SkillExecutionContext
    ) -> SkillResult:
        """顺序执行子技能"""
        if not self.skill_library:
            return SkillResult.error_result("技能库未设置")
        
        results = []
        accumulated_data = {}
        
        for step_idx, (skill_name, param_mapping) in enumerate(self.sub_skills):
            skill = self.skill_library.get_skill(skill_name)
            if not skill:
                return SkillResult.error_result(f"找不到子技能: {skill_name}")
            
            # 参数映射：将组合技能参数映射到子技能参数
            sub_params = {}
            for sub_param, parent_param in param_mapping.items():
                if parent_param.startswith("$"):
                    # 引用之前步骤的结果
                    ref_parts = parent_param[1:].split(".")
                    data = accumulated_data.get(ref_parts[0])
                    # 处理嵌套引用
                    for part in ref_parts[1:]:
                        if isinstance(data, dict):
                            data = data.get(part)
                        else:
                            data = None
                            break
                    sub_params[sub_param] = data
                else:
                    sub_params[sub_param] = params.get(parent_param)
            
            result = await skill.execute(sub_params, context)
            results.append(result)
            
            if not result.success:
                return SkillResult.error_result(
                    f"子技能 {skill_name} 执行失败: {result.error}",
                    data={"partial_results": results}
                )
            
            # 累积数据供后续步骤使用（使用步骤索引作为key）
            accumulated_data[f"step_{step_idx}"] = result.data
        
        return SkillResult.success_result({
            "results": accumulated_data,
            "execution_chain": [r.data for r in results]
        })
