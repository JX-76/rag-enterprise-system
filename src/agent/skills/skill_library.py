"""
技能库管理

支持技能的注册、发现、检索
"""
import json
from typing import Dict, List, Optional, Any
from datetime import datetime
import difflib

from .skill import Skill, SkillResult


class SkillLibrary:
    """
    技能库
    
    管理所有可用技能
    """
    
    def __init__(self):
        self._skills: Dict[str, Skill] = {}  # name -> Skill
        self._category_index: Dict[str, List[str]] = {}  # category -> [skill_names]
        self._tag_index: Dict[str, List[str]] = {}  # tag -> [skill_names]
        
        # 使用频次统计（用于技能推荐）
        self.usage_stats: Dict[str, int] = {}
    
    def register(self, skill: Skill) -> bool:
        """
        注册技能
        
        Args:
            skill: 技能实例
        
        Returns:
            bool: 是否注册成功
        """
        if skill.name in self._skills:
            print(f"技能 {skill.name} 已存在，将被覆盖")
        
        self._skills[skill.name] = skill
        
        # 更新分类索引
        if skill.category not in self._category_index:
            self._category_index[skill.category] = []
        if skill.name not in self._category_index[skill.category]:
            self._category_index[skill.category].append(skill.name)
        
        # 更新标签索引
        for tag in skill.tags:
            if tag not in self._tag_index:
                self._tag_index[tag] = []
            if skill.name not in self._tag_index[tag]:
                self._tag_index[tag].append(skill.name)
        
        # 初始化使用统计
        if skill.name not in self.usage_stats:
            self.usage_stats[skill.name] = 0
        
        return True
    
    def unregister(self, skill_name: str) -> bool:
        """注销技能"""
        if skill_name not in self._skills:
            return False
        
        skill = self._skills[skill_name]
        
        # 从分类索引移除
        if skill.category in self._category_index:
            if skill_name in self._category_index[skill.category]:
                self._category_index[skill.category].remove(skill_name)
        
        # 从标签索引移除
        for tag in skill.tags:
            if tag in self._tag_index:
                if skill_name in self._tag_index[tag]:
                    self._tag_index[tag].remove(skill_name)
        
        del self._skills[skill_name]
        return True
    
    def get_skill(self, name: str) -> Optional[Skill]:
        """获取技能"""
        return self._skills.get(name)
    
    def has_skill(self, name: str) -> bool:
        """检查技能是否存在"""
        return name in self._skills
    
    def list_skills(
        self,
        category: Optional[str] = None,
        tag: Optional[str] = None
    ) -> List[Skill]:
        """
        列出技能
        
        Args:
            category: 按分类筛选
            tag: 按标签筛选
        
        Returns:
            List[Skill]: 技能列表
        """
        if category:
            names = self._category_index.get(category, [])
            return [self._skills[name] for name in names if name in self._skills]
        
        if tag:
            names = self._tag_index.get(tag, [])
            return [self._skills[name] for name in names if name in self._skills]
        
        return list(self._skills.values())
    
    def search_skills(self, query: str, top_k: int = 5) -> List[tuple[Skill, float]]:
        """
        搜索技能
        
        使用名称和描述的相似度匹配
        
        Args:
            query: 搜索查询
            top_k: 返回数量
        
        Returns:
            List[(Skill, score)]: 技能及匹配分数
        """
        results = []
        query_lower = query.lower()
        
        for skill in self._skills.values():
            # 计算多种相似度
            name_sim = difflib.SequenceMatcher(
                None, query_lower, skill.name.lower()
            ).ratio()
            
            desc_sim = difflib.SequenceMatcher(
                None, query_lower, skill.description.lower()
            ).ratio()
            
            # 标签匹配
            tag_sim = 0
            for tag in skill.tags:
                if query_lower in tag.lower():
                    tag_sim = max(tag_sim, 0.5)
            
            # 综合分数
            score = max(name_sim * 1.5, desc_sim, tag_sim)
            
            if score > 0.3:  # 阈值
                results.append((skill, score))
        
        # 按分数排序
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]
    
    def recommend_skills(
        self,
        context: str,
        top_k: int = 3
    ) -> List[Skill]:
        """
        根据上下文推荐技能
        
        简单实现：基于使用频次 + 相似度
        
        Args:
            context: 当前上下文
            top_k: 推荐数量
        
        Returns:
            List[Skill]: 推荐技能
        """
        # 搜索相关技能
        searched = self.search_skills(context, top_k=10)
        
        # 计算综合分数（相似度 + 使用频次归一化 + 成功率）
        scored = []
        max_usage = max(self.usage_stats.values()) if self.usage_stats else 1
        
        for skill, sim_score in searched:
            usage_score = self.usage_stats.get(skill.name, 0) / max(max_usage, 1)
            success_score = skill.success_rate
            
            # 综合分数
            final_score = sim_score * 0.5 + usage_score * 0.3 + success_score * 0.2
            scored.append((skill, final_score))
        
        # 排序
        scored.sort(key=lambda x: x[1], reverse=True)
        return [skill for skill, _ in scored[:top_k]]
    
    def get_skill_schemas(self) -> List[dict]:
        """
        获取所有技能的Schema
        
        用于LLM函数调用
        """
        return [skill.get_param_schema() for skill in self._skills.values()]
    
    def get_categories(self) -> List[str]:
        """获取所有分类"""
        return list(self._category_index.keys())
    
    def get_tags(self) -> List[str]:
        """获取所有标签"""
        return list(self._tag_index.keys())
    
    def record_usage(self, skill_name: str):
        """记录技能使用"""
        self.usage_stats[skill_name] = self.usage_stats.get(skill_name, 0) + 1
    
    def get_popular_skills(self, top_k: int = 10) -> List[tuple[str, int]]:
        """获取热门技能"""
        sorted_stats = sorted(
            self.usage_stats.items(),
            key=lambda x: x[1],
            reverse=True
        )
        return sorted_stats[:top_k]
    
    def export_library(self, filepath: str):
        """导出技能库"""
        data = {
            "skills": [
                skill.to_dict()
                for skill in self._skills.values()
            ],
            "usage_stats": self.usage_stats,
            "export_time": datetime.now().isoformat()
        }
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def __len__(self) -> int:
        return len(self._skills)
    
    def __contains__(self, name: str) -> bool:
        return name in self._skills
