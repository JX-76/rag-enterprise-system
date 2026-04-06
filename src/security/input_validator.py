"""
Input Validator - 输入校验器
防止Prompt注入、XSS、敏感信息泄露
"""
import re
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass
import html

from src.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ValidationResult:
    """校验结果"""
    is_valid: bool
    sanitized_input: str
    errors: List[str]
    risk_level: str  # low, medium, high
    detected_issues: List[str]


class InputValidator:
    """
    输入校验器
    
    防护类型：
    1. Prompt注入攻击
    2. XSS攻击
    3. 敏感词过滤
    4. 超长输入限制
    5. 特殊字符过滤
    """
    
    # Prompt注入攻击模式
    PROMPT_INJECTION_PATTERNS = [
        r"ignore\s+(?:previous|above|all).*instruction",
        r"disregard\s+(?:previous|above|all).*instruction",
        r"system\s*:\s*you\s+are\s+now",
        r"new\s+instruction\s*:",
        r"override\s+(?:previous|security|restriction)",
        r"DAN\s*\(.*jailbreak",
        r"developer\s*mode",
        r"ignore\s+previous\s+prompts",
    ]
    
    # 敏感词列表（可扩展）
    SENSITIVE_KEYWORDS = [
        "password", "secret", "token", "api_key",
        "credit_card", "ssn", "身份证", "银行卡",
    ]
    
    # 危险的HTML标签
    DANGEROUS_HTML_TAGS = [
        "script", "iframe", "object", "embed", "form",
        "input", "textarea", "button", "onclick", "onerror",
    ]
    
    def __init__(
        self,
        max_length: int = 2000,
        allow_html: bool = False,
        strict_mode: bool = False
    ):
        self.max_length = max_length
        self.allow_html = allow_html
        self.strict_mode = strict_mode
        self._compile_patterns()
    
    def _compile_patterns(self):
        """编译正则表达式"""
        self._injection_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.PROMPT_INJECTION_PATTERNS
        ]
    
    def validate(
        self,
        input_text: str,
        context: Optional[str] = None
    ) -> ValidationResult:
        """
        校验输入
        
        Returns:
            ValidationResult: 校验结果
        """
        errors = []
        issues = []
        risk_score = 0
        
        original = input_text
        sanitized = input_text
        
        # 1. 长度检查
        if len(input_text) > self.max_length:
            if self.strict_mode:
                errors.append(f"Input exceeds maximum length of {self.max_length}")
                sanitized = input_text[:self.max_length]
            else:
                issues.append(f"Input truncated from {len(input_text)} to {self.max_length}")
                sanitized = input_text[:self.max_length]
            risk_score += 1
        
        # 2. Prompt注入检测
        injection_detected = self._detect_prompt_injection(sanitized)
        if injection_detected:
            errors.append("Potential prompt injection detected")
            issues.append(f"Injection pattern: {injection_detected}")
            sanitized = self._sanitize_prompt_injection(sanitized)
            risk_score += 3
        
        # 3. HTML/XSS检测
        if not self.allow_html:
            xss_detected = self._detect_xss(sanitized)
            if xss_detected:
                errors.append("Potential XSS content detected")
                sanitized = html.escape(sanitized)
                risk_score += 2
        
        # 4. 敏感词检测
        sensitive_found = self._detect_sensitive_words(sanitized)
        if sensitive_found:
            issues.append(f"Sensitive keywords detected: {sensitive_found}")
            risk_score += 1
        
        # 5. 特殊字符检测（严格模式）
        if self.strict_mode:
            sanitized = self._remove_special_chars(sanitized)
        
        # 确定风险等级
        if risk_score >= 3:
            risk_level = "high"
        elif risk_score >= 1:
            risk_level = "medium"
        else:
            risk_level = "low"
        
        is_valid = len(errors) == 0
        
        # 记录日志
        if issues or errors:
            logger.warning(
                f"Input validation: risk={risk_level}, "
                f"issues={len(issues)}, errors={len(errors)}"
            )
        
        return ValidationResult(
            is_valid=is_valid,
            sanitized_input=sanitized,
            errors=errors,
            risk_level=risk_level,
            detected_issues=issues
        )
    
    def _detect_prompt_injection(self, text: str) -> Optional[str]:
        """检测Prompt注入"""
        for pattern in self._injection_patterns:
            match = pattern.search(text)
            if match:
                return match.group(0)
        return None
    
    def _sanitize_prompt_injection(self, text: str) -> str:
        """清理Prompt注入内容"""
        sanitized = text
        for pattern in self._injection_patterns:
            sanitized = pattern.sub("[REMOVED]", sanitized)
        return sanitized
    
    def _detect_xss(self, text: str) -> bool:
        """检测XSS攻击"""
        # 检测HTML标签
        for tag in self.DANGEROUS_HTML_TAGS:
            pattern = rf"<{tag}[>\s]"
            if re.search(pattern, text, re.IGNORECASE):
                return True
        
        # 检测事件处理器
        if re.search(r"on\w+\s*=", text, re.IGNORECASE):
            return True
        
        # 检测javascript:协议
        if re.search(r"javascript:", text, re.IGNORECASE):
            return True
        
        return False
    
    def _detect_sensitive_words(self, text: str) -> List[str]:
        """检测敏感词"""
        found = []
        text_lower = text.lower()
        for word in self.SENSITIVE_KEYWORDS:
            if word.lower() in text_lower:
                found.append(word)
        return found
    
    def _remove_special_chars(self, text: str) -> str:
        """移除特殊字符"""
        # 保留常用字符，移除控制字符
        allowed = re.compile(r'[^\w\s\-.,!?;:\'"()[\]{}@#$%&*+=/\\]')
        return allowed.sub('', text)


def validate_query(
    query: str,
    max_length: int = 2000,
    strict: bool = False
) -> Tuple[bool, str, List[str]]:
    """
    快捷校验函数
    
    Returns:
        (是否通过, 清理后的文本, 错误列表)
    """
    validator = InputValidator(max_length=max_length, strict_mode=strict)
    result = validator.validate(query)
    return result.is_valid, result.sanitized_input, result.errors
