#!/usr/bin/env python3
"""
Arxiv论文数据集下载器
下载真实论文数据用于RAG实验

用法:
    python scripts/download_arxiv.py --category cs.AI --max 100 --output data/arxiv
    python scripts/download_arxiv.py --category cs.CL --max 50 --output data/arxiv
"""
import argparse
import asyncio
import json
import os
from pathlib import Path
from typing import List, Dict, Any
from dataclasses import dataclass, asdict
import xml.etree.ElementTree as ET

import aiohttp
import aiofiles


@dataclass
class ArxivPaper:
    """Arxiv论文数据结构"""
    id: str
    title: str
    abstract: str
    authors: List[str]
    categories: List[str]
    published: str
    pdf_url: str
    primary_category: str


class ArxivDownloader:
    """Arxiv论文下载器"""
    
    API_URL = "http://export.arxiv.org/api/query"
    
    def __init__(self, delay: float = 3.0):
        """
        Args:
            delay: 请求间隔（秒），避免被限流
        """
        self.delay = delay
        self.session = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def search_papers(
        self,
        category: str,
        max_results: int = 100,
        sort_by: str = "submittedDate",
        sort_order: str = "descending"
    ) -> List[ArxivPaper]:
        """
        搜索Arxiv论文
        
        Args:
            category: 论文分类，如 cs.AI, cs.CL, cs.LG
            max_results: 最大下载数量
            sort_by: 排序字段
            sort_order: 排序顺序
        """
        print(f"🔍 搜索分类: {category}, 数量: {max_results}")
        
        # 构建查询
        query = f"cat:{category}"
        params = {
            "search_query": query,
            "start": 0,
            "max_results": max_results,
            "sortBy": sort_by,
            "sortOrder": sort_order,
        }
        
        async with self.session.get(self.API_URL, params=params) as resp:
            if resp.status != 200:
                print(f"❌ 请求失败: {resp.status}")
                return []
            
            xml_content = await resp.text()
            papers = self._parse_xml(xml_content)
            
        print(f"✅ 找到 {len(papers)} 篇论文")
        return papers
    
    def _parse_xml(self, xml_content: str) -> List[ArxivPaper]:
        """解析XML响应"""
        papers = []
        
        # 处理命名空间
        ns = {
            'atom': 'http://www.w3.org/2005/Atom',
            'arxiv': 'http://arxiv.org/schemas/atom'
        }
        
        root = ET.fromstring(xml_content.encode('utf-8'))
        
        for entry in root.findall('atom:entry', ns):
            try:
                # 提取ID
                id_elem = entry.find('atom:id', ns)
                paper_id = id_elem.text.split('/')[-1] if id_elem else ""
                
                # 标题
                title_elem = entry.find('atom:title', ns)
                title = title_elem.text.strip() if title_elem else ""
                
                # 摘要
                summary_elem = entry.find('atom:summary', ns)
                abstract = summary_elem.text.strip() if summary_elem else ""
                
                # 作者
                authors = []
                for author in entry.findall('atom:author', ns):
                    name_elem = author.find('atom:name', ns)
                    if name_elem:
                        authors.append(name_elem.text)
                
                # 分类
                categories = []
                primary_category = ""
                for cat in entry.findall('atom:category', ns):
                    term = cat.get('term', '')
                    if term:
                        categories.append(term)
                
                # 主分类
                prim_cat_elem = entry.find('arxiv:primary_category', ns)
                if prim_cat_elem is not None:
                    primary_category = prim_cat_elem.get('term', '')
                
                # 发布日期
                published_elem = entry.find('atom:published', ns)
                published = published_elem.text[:10] if published_elem else ""
                
                # PDF链接
                pdf_url = f"https://arxiv.org/pdf/{paper_id}.pdf"
                
                paper = ArxivPaper(
                    id=paper_id,
                    title=title,
                    abstract=abstract,
                    authors=authors,
                    categories=categories,
                    published=published,
                    pdf_url=pdf_url,
                    primary_category=primary_category
                )
                papers.append(paper)
                
            except Exception as e:
                print(f"⚠️ 解析论文出错: {e}")
                continue
        
        return papers
    
    async def download_pdf(self, paper: ArxivPaper, output_dir: Path) -> bool:
        """下载PDF文件"""
        pdf_path = output_dir / f"{paper.id}.pdf"
        
        if pdf_path.exists():
            print(f"⏭️ 已存在: {paper.id}")
            return True
        
        try:
            async with self.session.get(paper.pdf_url) as resp:
                if resp.status == 200:
                    content = await resp.read()
                    async with aiofiles.open(pdf_path, 'wb') as f:
                        await f.write(content)
                    print(f"✅ 下载完成: {paper.id}")
                    return True
                else:
                    print(f"❌ 下载失败: {paper.id} (status {resp.status})")
                    return False
        except Exception as e:
            print(f"❌ 下载出错: {paper.id}, {e}")
            return False
    
    def save_metadata(self, papers: List[ArxivPaper], output_file: Path):
        """保存元数据"""
        metadata = [asdict(p) for p in papers]
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        print(f"💾 元数据已保存: {output_file}")


async def main():
    parser = argparse.ArgumentParser(description="Download Arxiv Papers")
    parser.add_argument("--category", default="cs.AI", help="Arxiv category (e.g., cs.AI, cs.CL)")
    parser.add_argument("--max", type=int, default=100, help="Max papers to download")
    parser.add_argument("--output", default="data/arxiv", help="Output directory")
    parser.add_argument("--download-pdf", action="store_true", help="Download PDF files")
    
    args = parser.parse_args()
    
    # 创建输出目录
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    async with ArxivDownloader(delay=3.0) as downloader:
        # 搜索论文
        papers = await downloader.search_papers(
            category=args.category,
            max_results=args.max
        )
        
        if not papers:
            print("❌ 未找到论文")
            return
        
        # 保存元数据
        metadata_file = output_dir / f"{args.category.replace('.', '_')}_metadata.json"
        downloader.save_metadata(papers, metadata_file)
        
        # 下载PDF（可选）
        if args.download_pdf:
            print(f"\n📥 开始下载PDF...")
            for i, paper in enumerate(papers):
                await downloader.download_pdf(paper, output_dir)
                if i < len(papers) - 1:
                    await asyncio.sleep(3)  # 避免被限流
        
        print(f"\n✅ 完成！数据保存在: {output_dir}")
        print(f"📊 论文数量: {len(papers)}")


if __name__ == "__main__":
    asyncio.run(main())
