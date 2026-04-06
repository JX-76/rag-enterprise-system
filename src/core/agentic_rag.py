"""
Agentic RAG - 智能代理驱动的RAG系统
支持自主查询规划、多轮检索、自我纠错
不再是简单的线性Pipeline，而是Agent驱动的决策流程
"""
import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Callable, AsyncIterator
import re

from src.core.logging import get_logger
from src.services.llm_service import get_llm_service

logger = get_logger(__name__)


class AgentState(Enum):
    """Agent状态"""
    IDLE = "idle"
    PLANNING = "planning"           # 规划查询
    RETRIEVING = "retrieving"       # 执行检索
    REASONING = "reasoning"         # 分析结果
    VERIFYING = "verifying"         # 验证答案
    COMPLETE = "complete"           # 完成
    ERROR = "error"                 # 出错


class QueryType(Enum):
    """查询类型"""
    FACTUAL = "factual"             # 事实查询（单次检索）
    COMPARATIVE = "comparative"     # 比较查询（多源对比）
    CAUSAL = "causal"               # 因果查询（推理链）
    PROCEDURAL = "procedural"       # 流程查询（步骤分解）
    AGGREGATION = "aggregation"     # 聚合查询（汇总计算）
    AMBIGUOUS = "ambiguous"         # 模糊查询（需要澄清）


@dataclass
class RetrievalStep:
    """检索步骤"""
    step_id: int
    query: str                      # 检索查询
    query_type: str                 # 查询类型
    rationale: str                  # 检索理由
    retrieved_docs: List[Dict] = field(default_factory=list)
    is_sufficient: bool = False     # 信息是否充足
    needs_refinement: bool = False  # 是否需要优化


@dataclass
class AgentTrace:
    """Agent执行轨迹"""
    trace_id: str
    original_query: str
    query_type: QueryType
    steps: List[RetrievalStep] = field(default_factory=list)
    final_answer: Optional[str] = None
    confidence: float = 0.0
    iterations: int = 0
    state: AgentState = AgentState.IDLE
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None


class QueryPlanner:
    """
    查询规划器
    
    分析用户查询，决定：
    1. 查询类型（事实/比较/因果/流程/聚合）
    2. 需要几次检索
    3. 每次检索的目标
    """
    
    PLANNING_PROMPT = """你是一位专业的查询分析专家。请分析以下用户查询，并提供结构化的检索计划。

用户查询: {query}

请分析：
1. 这是什么类型的查询？（factual/comparative/causal/procedural/aggregation/ambiguous）
2. 需要几次检索步骤？
3. 每次检索的目标是什么？
4. 可能需要哪些关键词或子查询？

请以JSON格式输出：
{{
    "query_type": "类型",
    "complexity_score": 1-10,
    "requires_multi_hop": true/false,
    "steps": [
        {{
            "step_id": 1,
            "sub_query": "具体检索查询",
            "rationale": "为什么需要这次检索",
            "expected_info": "期望获得什么信息"
        }}
    ],
    "keywords": ["关键词1", "关键词2"],
    "potential_ambiguities": ["可能的歧义点"]
}}
"""
    
    def __init__(self):
        self.llm = None
    
    async def _get_llm(self):
        if self.llm is None:
            self.llm = await get_llm_service()
        return self.llm
    
    async def plan(self, query: str) -> Dict:
        """规划查询策略"""
        llm = await self._get_llm()
        
        prompt = self.PLANNING_PROMPT.format(query=query)
        
        try:
            response = await llm.generate(
                prompt=prompt,
                temperature=0.3,
                max_tokens=1000
            )
            
            # 提取JSON
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                plan = json.loads(json_match.group())
                return plan
            else:
                # 回退：简单分析
                return self._simple_plan(query)
                
        except Exception as e:
            logger.error(f"Query planning failed: {e}")
            return self._simple_plan(query)
    
    def _simple_plan(self, query: str) -> Dict:
        """简单规划（回退方案）"""
        # 启发式分析
        query_lower = query.lower()
        
        if any(w in query_lower for w in ["比较", "区别", "vs", "difference", "compare"]):
            query_type = "comparative"
        elif any(w in query_lower for w in ["为什么", "原因", "cause", "why", "reason"]):
            query_type = "causal"
        elif any(w in query_lower for w in ["怎么", "如何", "步骤", "how to", "步骤"]):
            query_type = "procedural"
        elif any(w in query_lower for w in ["多少", "总和", "统计", "total", "sum", "count"]):
            query_type = "aggregation"
        else:
            query_type = "factual"
        
        return {
            "query_type": query_type,
            "complexity_score": 5,
            "requires_multi_hop": False,
            "steps": [
                {
                    "step_id": 1,
                    "sub_query": query,
                    "rationale": "直接检索",
                    "expected_info": "相关信息"
                }
            ],
            "keywords": query.split()[:5]
        }


class VerificationModule:
    """
    答案验证模块
    
    验证：
    1. 答案是否完整回答了问题
    2. 是否有幻觉或不确定的内容
    3. 是否需要补充检索
    """
    
    VERIFICATION_PROMPT = """请验证以下答案是否完整准确地回答了问题。

问题: {question}

答案: {answer}

参考文档:
{context}

请分析：
1. 答案是否完全回答了问题？（是/部分/否）
2. 答案中是否有无法验证的陈述？
3. 答案是否遗漏了重要信息？
4. 置信度评分（0-1）
5. 是否需要额外检索？如果需要，请提供补充查询

输出JSON格式：
{{
    "is_complete": true/false,
    "has_hallucination": true/false,
    "hallucination_parts": ["可能幻觉的内容"],
    "missing_info": ["遗漏的信息"],
    "confidence": 0.0-1.0,
    "needs_more_retrieval": true/false,
    "additional_queries": ["补充查询1", "补充查询2"]
}}
"""
    
    def __init__(self):
        self.llm = None
    
    async def _get_llm(self):
        if self.llm is None:
            self.llm = await get_llm_service()
        return self.llm
    
    async def verify(
        self,
        query: str,
        answer: str,
        context: List[str],
        iteration: int = 0,
        max_iterations: int = 3
    ) -> Dict:
        """验证答案质量"""
        if iteration >= max_iterations:
            return {
                "is_complete": True,
                "confidence": 0.7,
                "needs_more_retrieval": False
            }
        
        llm = await self._get_llm()
        
        context_text = "\n\n".join(context[:5])  # 限制上下文长度
        
        prompt = self.VERIFICATION_PROMPT.format(
            question=query,
            answer=answer,
            context=context_text
        )
        
        try:
            response = await llm.generate(
                prompt=prompt,
                temperature=0.2,
                max_tokens=800
            )
            
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                return result
            else:
                return {"is_complete": True, "confidence": 0.7, "needs_more_retrieval": False}
                
        except Exception as e:
            logger.error(f"Verification failed: {e}")
            return {"is_complete": True, "confidence": 0.6, "needs_more_retrieval": False}


class AgenticRAG:
    """
    Agentic RAG引擎
    
    核心流程：
    1. Query → 规划器分析查询类型和策略
    2. 执行多轮检索（自适应）
    3. 每轮评估信息充足性
    4. 生成答案并验证
    5. 如不足 → 补充检索
    6. 输出最终答案
    """
    
    def __init__(
        self,
        retriever: Callable,           # 检索函数
        generator: Callable,           # 生成函数
        max_iterations: int = 3,
        confidence_threshold: float = 0.8
    ):
        self.retriever = retriever
        self.generator = generator
        self.max_iterations = max_iterations
        self.confidence_threshold = confidence_threshold
        
        self.planner = QueryPlanner()
        self.verifier = VerificationModule()
        
        logger.info(f"AgenticRAG initialized: max_iter={max_iterations}")
    
    async def query(
        self,
        query: str,
        stream: bool = False
    ) -> AsyncIterator[Dict]:
        """
        执行Agentic查询
        
        Yields:
            {
                "type": "plan" | "retrieval" | "reasoning" | "verification" | "answer",
                "data": {...}
            }
        """
        trace = AgentTrace(
            trace_id=f"trace_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            original_query=query,
            query_type=QueryType.FACTUAL
        )
        trace.state = AgentState.PLANNING
        
        # Step 1: 查询规划
        yield {"type": "plan", "data": {"status": "planning", "query": query}}
        
        plan = await self.planner.plan(query)
        trace.query_type = QueryType(plan.get("query_type", "factual"))
        steps_plan = plan.get("steps", [])
        
        yield {
            "type": "plan",
            "data": {
                "query_type": trace.query_type.value,
                "complexity": plan.get("complexity_score", 5),
                "multi_hop": plan.get("requires_multi_hop", False),
                "steps_count": len(steps_plan)
            }
        }
        
        # Step 2-4: 迭代检索和验证
        all_contexts = []
        final_answer = None
        
        for iteration in range(self.max_iterations):
            trace.iterations = iteration + 1
            trace.state = AgentState.RETRIEVING
            
            # 执行检索步骤
            current_queries = []
            
            if iteration == 0:
                # 第一轮：按计划执行
                for step_plan in steps_plan:
                    current_queries.append({
                        "query": step_plan.get("sub_query", query),
                        "rationale": step_plan.get("rationale", "")
                    })
            else:
                # 后续轮次：验证器建议的补充查询
                if hasattr(self, '_additional_queries'):
                    for aq in self._additional_queries:
                        current_queries.append({
                            "query": aq,
                            "rationale": "补充检索"
                        })
            
            # 执行检索
            for i, q_info in enumerate(current_queries):
                yield {
                    "type": "retrieval",
                    "data": {
                        "step": i + 1,
                        "query": q_info["query"],
                        "rationale": q_info["rationale"]
                    }
                }
                
                # 调用检索器
                docs = await self.retriever(q_info["query"])
                
                step = RetrievalStep(
                    step_id=len(trace.steps) + 1,
                    query=q_info["query"],
                    query_type=trace.query_type.value,
                    rationale=q_info["rationale"],
                    retrieved_docs=docs
                )
                
                trace.steps.append(step)
                
                # 收集上下文
                for doc in docs:
                    content = doc.get("content", "")
                    if content not in all_contexts:
                        all_contexts.append(content)
                
                yield {
                    "type": "retrieval",
                    "data": {
                        "step": i + 1,
                        "found_docs": len(docs),
                        "total_contexts": len(all_contexts)
                    }
                }
            
            # Step 3: 生成答案
            trace.state = AgentState.REASONING
            
            yield {
                "type": "reasoning",
                "data": {"status": "generating", "context_size": len(all_contexts)}
            }
            
            final_answer = await self.generator(query, all_contexts)
            
            # Step 4: 验证答案
            trace.state = AgentState.VERIFYING
            
            yield {"type": "verification", "data": {"status": "checking"}}
            
            verification = await self.verifier.verify(
                query=query,
                answer=final_answer,
                context=all_contexts,
                iteration=iteration,
                max_iterations=self.max_iterations
            )
            
            confidence = verification.get("confidence", 0.0)
            needs_more = verification.get("needs_more_retrieval", False)
            
            yield {
                "type": "verification",
                "data": {
                    "confidence": confidence,
                    "is_complete": verification.get("is_complete", False),
                    "has_hallucination": verification.get("has_hallucination", False)
                }
            }
            
            # 检查是否满足条件
            if confidence >= self.confidence_threshold and not needs_more:
                trace.confidence = confidence
                break
            
            # 准备下一轮
            if needs_more and iteration < self.max_iterations - 1:
                self._additional_queries = verification.get("additional_queries", [])
                yield {
                    "type": "reasoning",
                    "data": {"status": "needs_more_info", "next_iteration": iteration + 2}
                }
            else:
                trace.confidence = confidence
                break
        
        # 完成
        trace.state = AgentState.COMPLETE
        trace.final_answer = final_answer
        trace.completed_at = datetime.now()
        
        yield {
            "type": "answer",
            "data": {
                "answer": final_answer,
                "confidence": trace.confidence,
                "iterations": trace.iterations,
                "total_docs": sum(len(s.retrieved_docs) for s in trace.steps),
                "trace_id": trace.trace_id
            }
        }
    
    async def query_sync(self, query: str) -> Dict:
        """同步方式执行查询（返回完整结果）"""
        results = []
        async for item in self.query(query):
            results.append(item)
        
        # 返回最终结果
        if results:
            return results[-1]["data"]
        return {}


class ToolUsingAgent:
    """
    工具使用Agent
    
    支持调用外部工具：
    - 搜索引擎
    - 计算器
    - 数据库查询
    - API调用
    """
    
    def __init__(self):
        self.tools = {}
    
    def register_tool(self, name: str, func: Callable, description: str):
        """注册工具"""
        self.tools[name] = {
            "func": func,
            "description": description
        }
    
    async def decide_and_use_tools(self, query: str) -> List[Dict]:
        """决定使用哪些工具"""
        # 启发式判断
        tools_to_use = []
        query_lower = query.lower()
        
        if any(w in query_lower for w in ["计算", "多少", "总和", "calculate", "sum", "total"]):
            if "calculator" in self.tools:
                tools_to_use.append("calculator")
        
        if any(w in query_lower for w in ["搜索", "最新", "search", "latest", "news"]):
            if "web_search" in self.tools:
                tools_to_use.append("web_search")
        
        # 执行工具
        results = []
        for tool_name in tools_to_use:
            tool = self.tools.get(tool_name)
            if tool:
                try:
                    result = await tool["func"](query)
                    results.append({
                        "tool": tool_name,
                        "result": result
                    })
                except Exception as e:
                    logger.error(f"Tool {tool_name} failed: {e}")
        
        return results
