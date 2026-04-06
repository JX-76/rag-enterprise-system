"""
Parent-Child Chunker - 父子分块策略
小块用于精确检索，大块用于完整上下文
"""
import hashlib
import re
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

from src.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ParentChunk:
    """父块 - 存储完整上下文"""
    id: str
    content: str
    start_pos: int
    end_pos: int
    metadata: Dict[str, Any] = field(default_factory=dict)
    children: List['ChildChunk'] = field(default_factory=list)
    
    def to_context(self) -> str:
        """转换为上下文格式"""
        return self.content


@dataclass
class ChildChunk:
    """子块 - 用于精确检索"""
    id: str
    content: str
    parent_id: str
    start_pos: int
    end_pos: int
    metadata: Dict[str, Any] = field(default_factory=dict)
    parent: Optional[ParentChunk] = None
    
    def get_full_context(self) -> str:
        """获取父块完整上下文"""
        if self.parent:
            return self.parent.to_context()
        return self.content


class ParentChildChunker:
    """
    父子分块器
    
    策略：
    1. 先按语义边界分割父块（大段落/章节）
    2. 在父块内滑动窗口生成子块（小切片）
    3. 检索时匹配子块，返回父块作为上下文
    
    优势：
    - 子块小 → 检索精度高
    - 父块大 → 上下文完整
    """
    
    def __init__(
        self,
        parent_size: int = 1000,      # 父块大小（token）
        child_size: int = 200,         # 子块大小（token）
        child_overlap: int = 40,       # 子块重叠（20%）
        parent_overlap: int = 100,     # 父块重叠
        tokenizer=None
    ):
        self.parent_size = parent_size
        self.child_size = child_size
        self.child_overlap = child_overlap
        self.parent_overlap = parent_overlap
        self.tokenizer = tokenizer
        
        logger.info(
            f"ParentChildChunker initialized: "
            f"parent={parent_size}, child={child_size}, overlap={child_overlap}"
        )
    
    def _estimate_tokens(self, text: str) -> int:
        """估算token数"""
        if self.tokenizer:
            return len(self.tokenizer.encode(text))
        # 粗略估算：1 token ≈ 0.75个汉字 或 4个英文字符
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        other_chars = len(text) - chinese_chars
        return int(chinese_chars / 0.75 + other_chars / 4)
    
    def _split_by_semantic_boundaries(
        self,
        text: str,
        target_size: int
    ) -> List[Tuple[int, int, str]]:
        """
        按语义边界分割文本
        
        优先级：
        1. 章节标题 (## 标题)
        2. 段落分隔 (\n\n)
        3. 句子分隔 (.。！？)
        4. 强制切分
        """
        chunks = []
        start = 0
        
        # 定义分隔符优先级
        patterns = [
            (r'\n#{1,6}\s+', 'heading'),      # Markdown标题
            (r'\n\n+', 'paragraph'),          # 段落
            (r'[.。！？]\s+', 'sentence'),     # 句子
        ]
        
        while start < len(text):
            remaining = text[start:]
            current_tokens = self._estimate_tokens(remaining)
            
            if current_tokens <= target_size:
                chunks.append((start, len(text), text[start:]))
                break
            
            # 在目标大小附近找最佳切分点
            target_pos = start + int(len(remaining) * (target_size / max(current_tokens, 1)))
            best_pos = None
            best_priority = float('inf')
            
            # 搜索范围内的所有分隔符
            search_start = max(start, target_pos - 200)
            search_end = min(len(text), target_pos + 200)
            
            for pattern, priority in patterns:
                for match in re.finditer(pattern, text[search_start:search_end]):
                    pos = search_start + match.end()
                    if pos > start and pos < len(text):
                        # 计算优先级得分（越接近目标位置越好）
                        distance = abs(pos - target_pos)
                        score = patterns.index((pattern, priority)) * 1000 + distance
                        if score < best_priority:
                            best_priority = score
                            best_pos = pos
            
            if best_pos and best_pos > start:
                chunks.append((start, best_pos, text[start:best_pos]))
                start = best_pos
            else:
                # 强制切分
                chunks.append((start, target_pos, text[start:target_pos]))
                start = target_pos
        
        return chunks
    
    def _create_sliding_windows(
        self,
        text: str,
        window_size: int,
        overlap: int
    ) -> List[Tuple[int, int, str]]:
        """创建滑动窗口子块"""
        windows = []
        step = window_size - overlap
        start = 0
        
        while start < len(text):
            end = min(start + window_size, len(text))
            windows.append((start, end, text[start:end]))
            
            if end >= len(text):
                break
            start += step
        
        return windows
    
    def chunk(self, text: str, doc_id: str = "", metadata: Dict = None) -> List[ParentChunk]:
        """
        执行父子分块
        
        Returns:
            父块列表，每个父块包含其子块
        """
        if not text or not text.strip():
            return []
        
        metadata = metadata or {}
        parents = []
        
        # Step 1: 创建父块
        parent_segments = self._split_by_semantic_boundaries(
            text, self.parent_size
        )
        
        for i, (start, end, content) in enumerate(parent_segments):
            parent_id = f"{doc_id}_p{i}" if doc_id else f"p{i}_{hashlib.md5(content.encode()).hexdigest()[:8]}"
            
            parent = ParentChunk(
                id=parent_id,
                content=content.strip(),
                start_pos=start,
                end_pos=end,
                metadata={
                    **metadata,
                    "chunk_index": i,
                    "total_chunks": len(parent_segments),
                    "level": "parent"
                }
            )
            
            # Step 2: 在父块内创建子块
            if self._estimate_tokens(content) > self.child_size:
                child_windows = self._create_sliding_windows(
                    content, self.child_size, self.child_overlap
                )
                
                for j, (c_start, c_end, c_content) in enumerate(child_windows):
                    child_id = f"{parent_id}_c{j}"
                    child = ChildChunk(
                        id=child_id,
                        content=c_content.strip(),
                        parent_id=parent_id,
                        start_pos=c_start,
                        end_pos=c_end,
                        metadata={
                            "parent_index": i,
                            "child_index": j,
                            "level": "child"
                        },
                        parent=parent
                    )
                    parent.children.append(child)
            else:
                # 父块较小，直接作为一个子块
                child = ChildChunk(
                    id=f"{parent_id}_c0",
                    content=content.strip(),
                    parent_id=parent_id,
                    start_pos=0,
                    end_pos=len(content),
                    metadata={
                        "parent_index": i,
                        "child_index": 0,
                        "level": "child"
                    },
                    parent=parent
                )
                parent.children.append(child)
            
            parents.append(parent)
        
        logger.info(
            f"Created {len(parents)} parent chunks with "
            f"{sum(len(p.children) for p in parents)} total children"
        )
        
        return parents
    
    def get_all_children(self, parents: List[ParentChunk]) -> List[ChildChunk]:
        """获取所有子块（用于索引）"""
        children = []
        for parent in parents:
            children.extend(parent.children)
        return children
    
    def reconstruct_context(
        self,
        child_chunks: List[ChildChunk],
        max_parents: int = 3
    ) -> List[str]:
        """
        根据命中的子块重构上下文
        
        策略：
        1. 去重父块
        2. 按原文顺序排列
        3. 返回完整父块内容
        """
        seen_parents = set()
        contexts = []
        
        for child in child_chunks:
            if child.parent and child.parent.id not in seen_parents:
                seen_parents.add(child.parent.id)
                contexts.append(child.get_full_context())
                
                if len(contexts) >= max_parents:
                    break
        
        return contexts


class HierarchicalDocumentSplitter:
    """
    层级文档分割器
    
    支持多层级结构：
    - 文档级 (Document)
    - 章节级 (Section)  
    - 段落级 (Paragraph)
    - 句子级 (Sentence)
    """
    
    def __init__(self):
        self.chunker = ParentChildChunker()
    
    def split_document(
        self,
        text: str,
        doc_id: str = "",
        doc_metadata: Dict = None
    ) -> Dict[str, Any]:
        """
        分层分割文档
        
        Returns:
            {
                "document": {"id": ..., "content": ...},
                "sections": [ParentChunk...],
                "chunks_for_indexing": [ChildChunk...],
                "statistics": {...}
            }
        """
        doc_metadata = doc_metadata or {}
        
        # 提取章节
        sections = self._extract_sections(text)
        
        all_parents = []
        for section in sections:
            parents = self.chunker.chunk(
                section["content"],
                doc_id=f"{doc_id}_{section['id']}",
                metadata={
                    **doc_metadata,
                    "section_title": section.get("title", ""),
                    "section_level": section.get("level", 1)
                }
            )
            all_parents.extend(parents)
        
        # 收集所有子块用于索引
        children = self.chunker.get_all_children(all_parents)
        
        stats = {
            "total_parents": len(all_parents),
            "total_children": len(children),
            "avg_children_per_parent": len(children) / max(len(all_parents), 1),
            "total_tokens": sum(
                len(c.content) for c in children
            )
        }
        
        return {
            "document": {
                "id": doc_id,
                "content": text[:1000] + "..." if len(text) > 1000 else text,
                "metadata": doc_metadata
            },
            "sections": all_parents,
            "chunks_for_indexing": children,
            "statistics": stats
        }
    
    def _extract_sections(self, text: str) -> List[Dict]:
        """提取文档章节结构"""
        # 匹配 Markdown 标题
        pattern = r'^(#{1,6})\s+(.+)$'
        
        sections = []
        current_section = {"id": "intro", "title": "Introduction", "content": "", "level": 0}
        
        for line in text.split('\n'):
            match = re.match(pattern, line.strip())
            if match:
                # 保存上一个章节
                if current_section["content"]:
                    sections.append(current_section)
                
                # 开始新章节
                hashes, title = match.groups()
                current_section = {
                    "id": f"sec_{len(sections)}",
                    "title": title.strip(),
                    "content": line + '\n',
                    "level": len(hashes)
                }
            else:
                current_section["content"] += line + '\n'
        
        # 保存最后一个章节
        if current_section["content"]:
            sections.append(current_section)
        
        # 如果没有章节，整体作为一个章节
        if not sections:
            sections = [{"id": "full", "title": "Full Document", "content": text, "level": 0}]
        
        return sections


# 便捷函数
def chunk_with_parent_child(
    text: str,
    doc_id: str = "",
    parent_size: int = 1000,
    child_size: int = 200
) -> Tuple[List[ParentChunk], List[ChildChunk]]:
    """
    快速父子分块
    
    Returns:
        (父块列表, 子块列表)
    """
    chunker = ParentChildChunker(
        parent_size=parent_size,
        child_size=child_size
    )
    
    parents = chunker.chunk(text, doc_id)
    children = chunker.get_all_children(parents)
    
    return parents, children
