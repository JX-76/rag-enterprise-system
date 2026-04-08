"""
文档解析模块单元测试
"""
import pytest
from pathlib import Path
import tempfile
import os

from src.document.parser import DocumentParser, ParseError


class TestDocumentParser:
    """文档解析器测试"""
    
    @pytest.fixture
    def parser(self):
        return DocumentParser()
    
    def test_validate_file_valid_pdf(self, parser):
        """测试有效的PDF文件校验"""
        # 模拟PDF文件头
        pdf_content = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n>>\nendobj\n"
        result = parser.validate_file(pdf_content, "application/pdf", "test.pdf")
        assert result == "pdf"
    
    def test_validate_file_valid_docx(self, parser):
        """测试有效的DOCX文件校验"""
        # DOCX文件以PK开头
        docx_content = b"PK\x03\x04\x14\x00\x00\x00\x08\x00"
        result = parser.validate_file(docx_content, "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "test.docx")
        assert result == "docx"
    
    def test_validate_file_valid_txt(self, parser):
        """测试有效的TXT文件校验"""
        txt_content = b"Hello World\nThis is a test."
        result = parser.validate_file(txt_content, "text/plain", "test.txt")
        assert result == "txt"
    
    def test_validate_file_invalid_format(self, parser):
        """测试无效格式文件"""
        invalid_content = b"invalid content"
        with pytest.raises(ParseError) as exc_info:
            parser.validate_file(invalid_content, "application/json", "test.json")
        assert "格式不支持" in str(exc_info.value)
    
    def test_validate_file_oversized(self, parser):
        """测试超大文件"""
        large_content = b"x" * (11 * 1024 * 1024)  # 11MB
        with pytest.raises(ParseError) as exc_info:
            parser.validate_file(large_content, "application/pdf", "large.pdf")
        assert "大小超过限制" in str(exc_info.value)
    
    def test_parse_txt_file(self, parser):
        """测试解析TXT文件"""
        content = b"Hello World\n\u4e2d\u6587\u6d4b\u8bd5"  # 包含中文
        result = parser.parse(content, "text/plain", "test.txt")
        assert result.text == "Hello World\n中文测试"
        assert result.title == "test"
        assert result.file_type == "txt"
    
    def test_parse_empty_content(self, parser):
        """测试空内容"""
        result = parser.parse(b"", "text/plain", "empty.txt")
        assert result.text == ""


class TestParseResult:
    """解析结果测试"""
    
    def test_parse_result_creation(self):
        """测试解析结果创建"""
        from src.document.parser import ParseResult
        result = ParseResult(
            text="test content",
            title="test",
            file_type="txt",
            metadata={"pages": 1}
        )
        assert result.text == "test content"
        assert result.title == "test"
        assert result.metadata == {"pages": 1}
