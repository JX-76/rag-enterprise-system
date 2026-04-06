"""
Agent 技能模块单元测试
"""
import pytest
import asyncio
from src.agent.skills.skill import (
    Skill, SkillParameter, ParameterType,
    SkillResult, SkillExecutionContext
)
from src.agent.skills.skill_library import SkillLibrary
from src.agent.skills.skill_executor import SkillExecutor
from src.agent.skills.builtin_skills import DocumentSearchSkill


class TestSkillParameter:
    """测试技能参数"""
    
    def test_string_validation(self):
        """测试字符串参数验证"""
        param = SkillParameter(
            name="query",
            description="搜索查询",
            type=ParameterType.STRING,
            required=True
        )
        
        # 有效值
        valid, error = param.validate("hello")
        assert valid
        
        # 无效类型
        valid, error = param.validate(123)
        assert not valid
        assert "应为字符串" in error
        
        # 必填但为空
        valid, error = param.validate(None)
        assert not valid
        assert "必填" in error
    
    def test_integer_validation(self):
        """测试整数参数验证"""
        param = SkillParameter(
            name="count",
            description="数量",
            type=ParameterType.INTEGER,
            required=False,
            default=5
        )
        
        # 使用默认值
        valid, error = param.validate(None)
        assert valid
        
        # 有效值
        valid, error = param.validate(10)
        assert valid
        
        # 无效类型
        valid, error = param.validate(10.5)
        assert not valid
    
    def test_enum_validation(self):
        """测试枚举参数验证"""
        param = SkillParameter(
            name="style",
            description="风格",
            type=ParameterType.STRING,
            enum=["concise", "detailed"]
        )
        
        valid, error = param.validate("concise")
        assert valid
        
        valid, error = param.validate("invalid")
        assert not valid
        assert "不在允许范围内" in error


class TestSkill:
    """测试技能基类"""
    
    @pytest.mark.asyncio
    async def test_document_search_skill(self):
        """测试文档搜索技能"""
        skill = DocumentSearchSkill()
        
        # 参数验证
        valid, error = skill.validate_params({"query": "test", "top_k": 5})
        assert valid
        
        # 缺少必填参数
        valid, error = skill.validate_params({})
        assert not valid
        assert "query" in error
        
        # 执行
        context = SkillExecutionContext(
            user_id="user1",
            session_id="session1"
        )
        result = await skill.execute({"query": "test"}, context)
        
        # 内置技能有 TODO，应该返回空结果而非报错
        assert isinstance(result, SkillResult)
    
    def test_skill_stats(self):
        """测试技能统计"""
        skill = DocumentSearchSkill()
        
        # 初始状态
        assert skill.success_rate == 1.0
        assert skill.avg_execution_time == 0.0
        
        # 更新统计
        skill.update_stats(success=True, execution_time=0.5)
        skill.update_stats(success=True, execution_time=0.3)
        skill.update_stats(success=False, execution_time=1.0)
        
        assert skill.execution_count == 3
        assert skill.success_count == 2
        assert abs(skill.success_rate - 0.667) < 0.01


class TestSkillLibrary:
    """测试技能库"""
    
    def test_register_and_get(self):
        """测试技能注册和获取"""
        library = SkillLibrary()
        skill = DocumentSearchSkill()
        
        library.register(skill)
        
        assert library.has_skill("document_search")
        assert library.get_skill("document_search") == skill
        assert len(library) == 1
    
    def test_search_skills(self):
        """测试技能搜索"""
        library = SkillLibrary()
        library.register(DocumentSearchSkill())
        
        results = library.search_skills("搜索", top_k=5)
        assert len(results) > 0
        assert results[0][0].name == "document_search"
    
    def test_recommend_skills(self):
        """测试技能推荐"""
        library = SkillLibrary()
        library.register(DocumentSearchSkill())
        
        # 模拟使用
        library.record_usage("document_search")
        library.record_usage("document_search")
        
        recommended = library.recommend_skills("查找文档", top_k=3)
        assert len(recommended) > 0


class TestSkillExecutor:
    """测试技能执行器"""
    
    @pytest.mark.asyncio
    async def test_execute_skill(self):
        """测试技能执行"""
        library = SkillLibrary()
        library.register(DocumentSearchSkill())
        
        executor = SkillExecutor(skill_library=library)
        context = SkillExecutionContext(
            user_id="user1",
            session_id="session1"
        )
        
        result = await executor.execute_skill(
            "document_search",
            {"query": "test"},
            context
        )
        
        assert isinstance(result, SkillResult)
        assert result.success or result.error is not None
    
    @pytest.mark.asyncio
    async def test_execute_nonexistent_skill(self):
        """测试执行不存在的技能"""
        library = SkillLibrary()
        executor = SkillExecutor(skill_library=library)
        context = SkillExecutionContext(
            user_id="user1",
            session_id="session1"
        )
        
        result = await executor.execute_skill(
            "nonexistent",
            {},
            context
        )
        
        assert not result.success
        assert "不存在" in result.error
    
    @pytest.mark.asyncio
    async def test_execute_plan(self):
        """测试执行计划"""
        library = SkillLibrary()
        library.register(DocumentSearchSkill())
        
        executor = SkillExecutor(skill_library=library)
        context = SkillExecutionContext(
            user_id="user1",
            session_id="session1"
        )
        
        plan = [
            {"skill": "document_search", "params": {"query": "test"}}
        ]
        
        results = await executor.execute_plan(plan, context)
        assert len(results) == 1
