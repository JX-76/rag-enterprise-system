"""
语义分块模块
按段落/句子拆分，保留语义完整性，支持重叠
"""
import re
import hashlib
from typing import List, Dict, Any
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


@dataclass
class TextChunk:
    """文本块"""
    id: str
    text: str
    start_pos: int
    end_pos: int
    metadata: Dict[str, Any] = field(default_factory=dict)


class SemanticChunker:
    """
    语义分块器
    
    策略：
    1. 按段落、句子边界切分，保留语义完整性
    2. 长段落按句子拆分，短段落不拆分
    3. 块间重叠保留上下文
    """
    
    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 64):
        """
        Args:
            chunk_size: 目标块大小（字符数）
            chunk_overlap: 块间重叠（字符数）
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        
        # 句子结束标点
        self.sentence_endings = r'[。！？.!?；;]'
    
    def chunk(self, text: str, doc_id: str = "") -> List[TextChunk]:
        """
        分块主函数
        
        Args:
            text: 原始文本
            doc_id: 文档ID，用于生成块ID
        
        Returns:
            文本块列表
        """
        if not text.strip():
            return []
        
        # 清理文本
        text = self._clean_text(text)
        
        # 短文本不拆分
        if len(text) <= self.chunk_size:
            chunk_id = self._generate_chunk_id(doc_id, text, 0)
            return [TextChunk(
                id=chunk_id,
                text=text,
                start_pos=0,
                end_pos=len(text)
            )]
        
        # 按段落拆分
        paragraphs = self._split_paragraphs(text)
        
        # 合并段落为块
        chunks = self._merge_paragraphs(paragraphs, doc_id)
        
        logger.info(f"分块完成: {len(text)} 字符 → {len(chunks)} 块")
        return chunks
    
    def _clean_text(self, text: str) -> str:
        """清理文本"""
        # 统一换行符
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        # 移除多余空行
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()
    
    def _split_paragraphs(self, text: str) -> List[str]:
        """按段落拆分"""
        # 按多个换行符分割段落
        paragraphs = re.split(r'\n\n+', text)
        return [p.strip() for p in paragraphs if p.strip()]
    
    def _merge_paragraphs(self, paragraphs: List[str], doc_id: str) -> List[TextChunk]:
        """合并段落为块"""
        chunks = []
        current_chunk = ""
        current_start = 0
        position = 0
        
        for para in paragraphs:
            para_len = len(para)
            
            # 如果当前段落很短，直接追加
            if para_len <= self.chunk_size // 2:
                if len(current_chunk) + para_len + 2 <= self.chunk_size:
                    if current_chunk:
                        current_chunk += "\n\n" + para
                    else:
                        current_chunk = para
                        current_start = position
                else:
                    # 保存当前块
                    if current_chunk:
                        chunks.append(self._create_chunk(
                            current_chunk, current_start, position, doc_id
                        ))
                    # 重叠处理
                    overlap_text = self._get_overlap_text(current_chunk)
                    current_chunk = overlap_text + "\n\n" + para if overlap_text else para
                    current_start = position - len(overlap_text) if overlap_text else position
            
            # 长段落需要拆分
            else:
                # 先保存当前块
                if current_chunk:
                    chunks.append(self._create_chunk(
                        current_chunk, current_start, position, doc_id
                    ))
                    overlap_text = self._get_overlap_text(current_chunk)
                    position -= len(overlap_text)
                else:
                    overlap_text = ""
                
                # 拆分长段落
                para_chunks = self._split_long_paragraph(para, doc_id, position)
                chunks.extend(para_chunks)
                
                # 更新位置
                if para_chunks:
                    position = para_chunks[-1].end_pos
                    # 最后一块可能还有空间，继续合并
                    current_chunk = para_chunks[-1].text
                    current_start = para_chunks[-1].start_pos
                    # 从列表中移除最后一块（会被覆盖或保留）
                    chunks.pop()
                else:
                    current_chunk = ""
            
            position += para_len + 2  # +2 for \n\n
        
        # 保存最后一块
        if current_chunk:
            chunks.append(self._create_chunk(
                current_chunk, current_start, position, doc_id
            ))
        
        return chunks
    
    def _split_long_paragraph(self, paragraph: str, doc_id: str, start_pos: int) -> List[TextChunk]:
        """拆分长段落为句子"""
        chunks = []
        
        # 按句子拆分
        sentences = re.split(f'({self.sentence_endings})', paragraph)
        # 重组句子（标点符号归到前一句）
        sentences = self._rebuild_sentences(sentences)
        
        current_chunk = ""
        current_start = start_pos
        position = start_pos
        
        for sent in sentences:
            sent = sent.strip()
            if not sent:
                continue
            
            if len(current_chunk) + len(sent) + 1 <= self.chunk_size:
                if current_chunk:
                    current_chunk += sent
                else:
                    current_chunk = sent
                    current_start = position
            else:
                # 保存当前块
                if current_chunk:
                    chunks.append(self._create_chunk(
                        current_chunk, current_start, position, doc_id
                    ))
                    # 重叠处理
                    overlap_text = self._get_overlap_text(current_chunk)
                    current_chunk = overlap_text + sent if overlap_text else sent
                    current_start = position - len(overlap_text) if overlap_text else position
                else:
                    # 单句就超长，强行切分
                    current_chunk = sent[:self.chunk_size]
                    current_start = position
            
            position += len(sent)
        
        # 保存最后一块
        if current_chunk:
            chunks.append(self._create_chunk(
                current_chunk, current_start, position, doc_id
            ))
        
        return chunks
    
    def _rebuild_sentences(self, parts: List[str]) -> List[str]:
        """重组句子（标点归到前一句）"""
        sentences = []
        i = 0
        while i < len(parts):
            if i + 1 < len(parts) and re.match(self.sentence_endings, parts[i + 1]):
                sentences.append(parts[i] + parts[i + 1])
                i += 2
            else:
                if parts[i].strip():
                    sentences.append(parts[i])
                i += 1
        return sentences
    
    def _get_overlap_text(self, text: str) -> str:
        """获取重叠文本"""
        if not text or self.chunk_overlap <= 0:
            return ""
        
        if len(text) <= self.chunk_overlap:
            return text
        
        # 从后往前找，尽量在句子边界处截断
        overlap_start = len(text) - self.chunk_overlap
        # 向后调整到句子开始
        for i in range(overlap_start, min(overlap_start + 50, len(text))):
            if i < len(text) and text[i] in '。！？.!?\n':
                overlap_start = i + 1
                break
        
        return text[overlap_start:]
    
    def _create_chunk(self, text: str, start: int, end: int, doc_id: str) -> TextChunk:
        """创建文本块"""
        chunk_id = self._generate_chunk_id(doc_id, text, start)
        return TextChunk(
            id=chunk_id,
            text=text.strip(),
            start_pos=start,
            end_pos=end
        )
    
    def _generate_chunk_id(self, doc_id: str, text: str, position: int) -> str:
        """生成块ID"""
        hash_input = f"{doc_id}:{text[:100]}:{position}"
        hash_value = hashlib.md5(hash_input.encode()).hexdigest()[:12]
        return f"chunk_{doc_id}_{hash_value}"


# 便捷函数
def chunk_text(text: str, chunk_size: int = 512, chunk_overlap: int = 64, doc_id: str = "") -> List[TextChunk]:
    """便捷分块函数"""
    chunker = SemanticChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    return chunker.chunk(text, doc_id)