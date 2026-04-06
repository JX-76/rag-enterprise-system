"""
Agent 技能库

支持：
1. 技能注册与发现
2. 技能参数自动生成
3. 技能组合与编排
4. 技能执行与结果校验
5. 技能学习与优化（RL基础）
"""
from .skill import Skill, SkillParameter, SkillResult, SkillExecutionContext
from .skill_library import SkillLibrary
from .skill_executor import SkillExecutor
from .builtin_skills import get_builtin_skills

__all__ = [
    'Skill',
    'SkillParameter',
    'SkillResult',
    'SkillExecutionContext',
    'SkillLibrary',
    'SkillExecutor',
    'get_builtin_skills'
]
