#!/usr/bin/env python3
"""
从Arxiv论文生成问答对
用于RAG系统的真实评估

用法:
    python scripts/generate_qa_pairs.py --input data/arxiv/cs_AI_metadata.json --output data/qa_pairs.json
"""
import argparse
import json
import random
from pathlib import Path
from typing import List, Dict, Any


class QAPairGenerator:
    """问答对生成器"""
    
    def __init__(self):
        self.templates = {
            "what": [
                "什么是{topic}？",
                "请解释{topic}的概念",
                "{topic}的定义是什么？",
            ],
            "how": [
                "如何实现{topic}？",
                "{topic}的方法有哪些？",
                "怎样才能{topic}？",
            ],
            "why": [
                "为什么需要{topic}？",
                "{topic}的意义是什么？",
                "为什么要研究{topic}？",
            ],
            "compare": [
                "{topic1}和{topic2}有什么区别？",
                "对比{topic1}与{topic2}",
                "{topic1}相比{topic2}的优势？",
            ],
        }
    
    def generate_from_title(self, title: str, paper_id: str) -> List[Dict[str, Any]]:
        """从论文标题生成问答对"""
        qa_pairs = []
        
        # 提取关键词（简化处理）
        keywords = self._extract_keywords(title)
        
        if len(keywords) >= 1:
            # What类型
            for template in random.sample(self.templates["what"], 1):
                qa_pairs.append({
                    "question": template.format(topic=keywords[0]),
                    "answer": f"根据论文《{title}》，{keywords[0]}是...",
                    "paper_id": paper_id,
                    "type": "what",
                    "source": "title"
                })
        
        if len(keywords) >= 2:
            # Compare类型
            for template in random.sample(self.templates["compare"], 1):
                qa_pairs.append({
                    "question": template.format(topic1=keywords[0], topic2=keywords[1]),
                    "answer": f"论文《{title}》对比了{keywords[0]}和{keywords[1]}...",
                    "paper_id": paper_id,
                    "type": "compare",
                    "source": "title"
                })
        
        return qa_pairs
    
    def generate_from_abstract(self, abstract: str, paper_id: str) -> List[Dict[str, Any]]:
        """从摘要生成问答对"""
        qa_pairs = []
        
        # 提取第一句作为问题
        sentences = abstract.split('. ')
        if len(sentences) >= 2:
            # 摘要通常第一句是背景，第二句是方法
            qa_pairs.append({
                "question": f"这篇论文提出了什么方法？",
                "answer": sentences[1] if len(sentences[1]) < 500 else sentences[1][:500],
                "paper_id": paper_id,
                "type": "method",
                "source": "abstract"
            })
        
        return qa_pairs
    
    def _extract_keywords(self, text: str) -> List[str]:
        """提取关键词（简化版）"""
        # 移除常见词
        stop_words = {'a', 'an', 'the', 'for', 'of', 'in', 'on', 'with', 'using', 'via'}
        words = text.lower().replace(':', '').replace(',', '').split()
        keywords = [w for w in words if len(w) > 3 and w not in stop_words]
        
        # 返回前2-3个较长的词
        return list(dict.fromkeys(keywords))[:3]  # 去重后取前3


def main():
    parser = argparse.ArgumentParser(description="Generate QA pairs from Arxiv papers")
    parser.add_argument("--input", required=True, help="Input metadata JSON file")
    parser.add_argument("--output", default="data/qa_pairs.json", help="Output QA pairs file")
    parser.add_argument("--max", type=int, default=100, help="Max QA pairs to generate")
    
    args = parser.parse_args()
    
    input_file = Path(args.input)
    output_file = Path(args.output)
    
    if not input_file.exists():
        print(f"❌ 输入文件不存在: {input_file}")
        return
    
    # 加载论文数据
    with open(input_file, 'r', encoding='utf-8') as f:
        papers = json.load(f)
    
    print(f"📚 加载了 {len(papers)} 篇论文")
    
    # 生成问答对
    generator = QAPairGenerator()
    all_qa_pairs = []
    
    for paper in papers:
        paper_id = paper.get('id', '')
        title = paper.get('title', '')
        abstract = paper.get('abstract', '')
        
        # 从标题生成
        qa_from_title = generator.generate_from_title(title, paper_id)
        all_qa_pairs.extend(qa_from_title)
        
        # 从摘要生成
        qa_from_abstract = generator.generate_from_abstract(abstract, paper_id)
        all_qa_pairs.extend(qa_from_abstract)
        
        if len(all_qa_pairs) >= args.max * 2:
            break
    
    # 随机选择指定数量
    if len(all_qa_pairs) > args.max:
        all_qa_pairs = random.sample(all_qa_pairs, args.max)
    
    # 保存
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_qa_pairs, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 生成了 {len(all_qa_pairs)} 个问答对")
    print(f"💾 保存到: {output_file}")
    
    # 显示样例
    print("\n📋 样例问答对:")
    for i, qa in enumerate(all_qa_pairs[:3], 1):
        print(f"\n{i}. Q: {qa['question']}")
        print(f"   A: {qa['answer'][:100]}...")


if __name__ == "__main__":
    main()
