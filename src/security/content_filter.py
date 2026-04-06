"""
Content Filter - 内容过滤器
过滤生成内容中的不当信息
"""
import re
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass

from src.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class FilterResult:
    """过滤结果"""
    is_safe: bool
    filtered_content: str
    violations: List[str]
    confidence: float


class ContentFilter:
    """
    内容过滤器
    
    过滤类型：
    1. 不当内容（暴力、色情、歧视等）
    2. 个人隐私信息
    3. 虚假信息标记
    4. 格式规范检查
    """
    
    # 不当内容模式（简化版，实际应用需要更完善的规则）
    INAPPROPRIATE_PATTERNS = {
        "violence": [
            r"\b(kill|murder|attack|violence)\b",
        ],
        "hate_speech": [
            r"\b(hate|racist|discriminat)\b",
        ],
        "harassment": [
            r"\b(harass|bully|threat)\b",
        ],
    }
    
    # 个人隐私模式
    PII_PATTERNS = {
        "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
        "phone": r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b",
        "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
        "credit_card": r"\b(?:\d{4}[-\s]?){3}\d{4}\b",
    }
    
    def __init__(
        self,
        filter_inappropriate: bool = True,
        filter_pii: bool = True,
        mask_pii: bool = True
    ):
        self.filter_inappropriate = filter_inappropriate
        self.filter_pii = filter_pii
        self.mask_pii = mask_pii
        self._compile_patterns()
    
    def _compile_patterns(self):
        """编译正则表达式"""
        self._inappropriate_regex = {}
        for category, patterns in self.INAPPROPRIATE_PATTERNS.items():
            self._inappropriate_regex[category] = [
                re.compile(p, re.IGNORECASE) for p in patterns
            ]
        
        self._pii_regex = {}
        for pii_type, pattern in self.PII_PATTERNS.items():
            self._pii_regex[pii_type] = re.compile(pattern)
    
    def filter(self, content: str) -> FilterResult:
        """
        过滤内容
        
        Returns:
            FilterResult: 过滤结果
        """
        violations = []
        filtered = content
        confidence = 1.0
        is_safe = True
        
        # 1. 不当内容检测
        if self.filter_inappropriate:
            inappropriate_found = self._detect_inappropriate(content)
            if inappropriate_found:
                violations.extend([f"Inappropriate: {v}" for v in inappropriate_found])
                confidence -= 0.3 * len(inappropriate_found)
                is_safe = False
        
        # 2. 个人隐私检测
        if self.filter_pii:
            pii_found = self._detect_pii(content)
            if pii_found:
                violations.extend([f"PII: {v[0]}" for v in pii_found])
                if self.mask_pii:
                    filtered = self._mask_pii(filtered, pii_found)
                confidence -= 0.2 * len(pii_found)
        
        # 3. 格式规范检查
        format_issues = self._check_format(filtered)
        if format_issues:
            violations.extend(format_issues)
        
        confidence = max(0.0, confidence)
        
        if violations:
            logger.warning(f"Content filter triggered: {violations}")
        
        return FilterResult(
            is_safe=is_safe,
            filtered_content=filtered,
            violations=violations,
            confidence=confidence
        )
    
    def _detect_inappropriate(self, content: str) -> List[str]:
        """检测不当内容"""
        found = []
        for category, patterns in self._inappropriate_regex.items():
            for pattern in patterns:
                if pattern.search(content):
                    found.append(category)
                    break
        return found
    
    def _detect_pii(self, content: str) -> List[Tuple[str, str]]:
        """检测个人隐私信息"""
        found = []
        for pii_type, pattern in self._pii_regex.items():
            matches = pattern.findall(content)
            for match in matches:
                found.append((pii_type, match))
        return found
    
    def _mask_pii(self, content: str, pii_list: List[Tuple[str, str]]) -> str:
        """遮盖PII"""
        masked = content
        for pii_type, value in pii_list:
            mask = f"[{pii_type.upper()}_REDACTED]"
            masked = masked.replace(value, mask)
        return masked
    
    def _check_format(self, content: str) -> List[str]:
        """检查格式规范"""
        issues = []
        
        # 检查过长无空格文本（可能是乱码）
        if len(content) > 100:
            no_space_parts = content.split()
            for part in no_space_parts:
                if len(part) > 100:
                    issues.append("Unusually long word detected")
                    break
        
        # 检查重复字符（可能是垃圾内容）
        if re.search(r'(.)\1{10,}', content):
            issues.append("Repeated characters detected")
        
        return issues
    
    def check_hallucination_signals(self, content: str, contexts: List[str]) -> Dict[str, Any]:
        """
        检查幻觉信号
        
        检测生成内容是否与上下文不一致
        """
        signals = {
            "has_contradiction": False,
            "unsupported_claims": [],
            "confidence": 1.0
        }
        
        # 检查是否包含"我不知道"等低置信度表达
        uncertainty_patterns = [
            r"\b(I don't know|I'm not sure|I cannot|我不确定|我不知道)\b",
            r"\b(no information|没有信息|无法找到)\b",
        ]
        
        for pattern in uncertainty_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                signals["confidence"] -= 0.3
        
        # 检查是否有具体声明但上下文为空
        if contexts and len(contexts) == 0:
            # 如果生成了具体内容但没有上下文支撑
            if len(content) > 50 and not any(u in content.lower() for u in ["don't know", "not sure", "不确定"]):
                signals["has_contradiction"] = True
                signals["unsupported_claims"].append("Generated content without context support")
        
        return signals
