"""
RAG生成模块
Prompt工程 + 幻觉检测基础版
"""
from typing import List, Dict, Any
import logging

from ..llm.base import LLMBase, LLMResponse
from .retriever import RetrievalResult

try:
    from sentence_transformers import SentenceTransformer
    from sklearn.metrics.pairwise import cosine_similarity
    EMBEDDING_AVAILABLE = True
except ImportError:
    EMBEDDING_AVAILABLE = False

logger = logging.getLogger(__name__)


# RAG Prompt模板
RAG_PROMPT_TEMPLATE = """你是一位专业助手。请仅基于以下检索到的文档内容回答问题。
如果文档中没有相关信息，请明确回答"未找到相关信息"，不要编造。

=== 检索到的文档 ===
{context}

=== 用户问题 ===
{question}

=== 回答要求 ===
1. 仅使用文档中的信息
2. 如果文档不相关，回答"未找到相关信息"
3. 回答简洁准确，控制在500字以内
4. 如有多个相关信息，综合回答

请回答："""


class RAGGenerator:
    """
    RAG生成器
    
    功能：
    1. Prompt工程 - 约束模型基于文档回答
    2. 幻觉检测 - 基础版（文本相似度）
    3. 置信度判断 - 检索结果质量评估
    """
    
    def __init__(
        self,
        llm: LLMBase,
        embedding_model: str = "BAAI/bge-small-zh-v1.5",
        hallucination_threshold: float = 0.5,
        retrieval_threshold: float = 0.7
    ):
        """
        Args:
            llm: 大模型实例
            embedding_model: 用于幻觉检测的embedding模型
            hallucination_threshold: 幻觉检测阈值
            retrieval_threshold: 检索置信度阈值
        """
        self.llm = llm
        self.hallucination_threshold = hallucination_threshold
        self.retrieval_threshold = retrieval_threshold
        self.embedding_model = None
        
        # 加载embedding模型（用于幻觉检测）
        if EMBEDDING_AVAILABLE:
            try:
                self.embedding_model = SentenceTransformer(embedding_model)
                logger.info(f"幻觉检测模型加载成功: {embedding_model}")
            except Exception as e:
                logger.warning(f"幻觉检测模型加载失败: {e}")
        else:
            logger.warning("sentence-transformers未安装，幻觉检测不可用")
    
    def generate(
        self,
        question: str,
        retrieval_results: List[RetrievalResult],
        temperature: float = 0.3
    ) -> Dict[str, Any]:
        """
        生成回答
        
        Args:
            question: 用户问题
            retrieval_results: 检索结果
            temperature: 生成温度
        
        Returns:
            包含answer、sources、hallucination_check的字典
        """
        # 检查检索质量
        if not retrieval_results:
            return {
                "answer": "未找到相关信息",
                "sources": [],
                "hallucination_check": {
                    "is_hallucination": False,
                    "confidence": 0.0,
                    "reason": "无检索结果"
                },
                "retrieval_quality": "low"
            }
        
        # 检查最高相似度
        top_score = max([r.score for r in retrieval_results]) if retrieval_results else 0
        if top_score < self.retrieval_threshold:
            logger.warning(f"检索置信度低: {top_score:.2f}")
            return {
                "answer": "未找到相关信息（检索置信度低）",
                "sources": [],
                "hallucination_check": {
                    "is_hallucination": False,
                    "confidence": top_score,
                    "reason": f"检索置信度低于阈值({self.retrieval_threshold})"
                },
                "retrieval_quality": "low"
            }
        
        # 构建Prompt
        context = self._build_context(retrieval_results)
        prompt = RAG_PROMPT_TEMPLATE.format(
            context=context,
            question=question
        )
        
        # 调用LLM
        try:
            response = self.llm.generate(prompt, temperature=temperature, max_tokens=1024)
            answer = response.text.strip()
        except Exception as e:
            logger.error(f"生成失败: {e}")
            return {
                "answer": "生成回答时出错，请稍后重试",
                "sources": [],
                "hallucination_check": {
                    "is_hallucination": False,
                    "confidence": 0.0,
                    "reason": f"生成失败: {str(e)}"
                },
                "retrieval_quality": "error"
            }
        
        # 幻觉检测
        hallucination_check = self._detect_hallucination(
            answer,
            [r.text for r in retrieval_results]
        )
        
        # 构建来源
        sources = [{
            "id": r.id,
            "text": r.text[:200] + "..." if len(r.text) > 200 else r.text,
            "score": r.score,
            "metadata": r.metadata
        } for r in retrieval_results[:3]]
        
        return {
            "answer": answer,
            "sources": sources,
            "hallucination_check": hallucination_check,
            "retrieval_quality": "good" if top_score >= self.retrieval_threshold else "medium"
        }
    
    def _build_context(self, retrieval_results: List[RetrievalResult]) -> str:
        """构建上下文"""
        contexts = []
        for i, result in enumerate(retrieval_results[:5], 1):  # 最多5个
            contexts.append(f"【文档{i}】\n{result.text}\n")
        
        return "\n".join(contexts)
    
    def _detect_hallucination(
        self,
        answer: str,
        source_texts: List[str]
    ) -> Dict[str, Any]:
        """
        幻觉检测基础版
        
        方法：计算回答与来源文档的相似度
        低于阈值则标记为疑似幻觉
        
        局限性：简单文本匹配，非语义NLI
        """
        if not EMBEDDING_AVAILABLE or not self.embedding_model:
            return {
                "is_hallucination": False,
                "confidence": 1.0,
                "reason": "幻觉检测未启用（模型未加载）"
            }
        
        try:
            # 编码
            answer_emb = self.embedding_model.encode([answer])
            source_emb = self.embedding_model.encode(source_texts)
            
            # 计算与每个来源的相似度
            similarities = cosine_similarity(answer_emb, source_emb)[0]
            max_similarity = float(max(similarities))
            
            # 判断
            is_hallucination = max_similarity < self.hallucination_threshold
            
            return {
                "is_hallucination": is_hallucination,
                "confidence": max_similarity,
                "reason": f"与来源文档最大相似度: {max_similarity:.2f}"
            }
            
        except Exception as e:
            logger.error(f"幻觉检测失败: {e}")
            return {
                "is_hallucination": False,
                "confidence": 0.0,
                "reason": f"检测失败: {str(e)}"
            }


# 便捷函数
def generate_answer(
    llm: LLMBase,
    question: str,
    retrieval_results: List[RetrievalResult],
    temperature: float = 0.3
) -> Dict[str, Any]:
    """便捷生成函数"""
    generator = RAGGenerator(llm)
    return generator.generate(question, retrieval_results, temperature)
