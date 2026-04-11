#!/usr/bin/env python3
"""
快速实验 - 5分钟跑完一组对比
适合快速验证某个想法

用法:
    python scripts/quick_experiment.py
"""
import asyncio
import json
import time
from typing import List, Dict, Any

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


class QuickRAGExperiment:
    """快速RAG实验"""
    
    def __init__(self):
        # 模拟查询和答案
        self.queries = [
            "什么是RAG？",
            "如何优化大模型推理？",
            "向量数据库有哪些？",
        ]
        self.ground_truth = [
            {"doc_rag_001", "doc_rag_002"},
            {"doc_opt_001", "doc_opt_003"},
            {"doc_db_001", "doc_db_002", "doc_db_005"},
        ]
    
    def simulate_retrieve(self, query: str, strategy: str) -> List[Dict]:
        """模拟检索结果"""
        # 不同策略的模拟质量
        quality = {
            "baseline": 0.6,
            "improved": 0.8,
        }.get(strategy, 0.6)
        
        results = []
        for i in range(5):
            score = quality * (1 - i * 0.15)
            results.append({
                "id": f"doc_{strategy}_{i}",
                "score": max(0.1, score),
                "content": f"Result {i}"
            })
        return results
    
    def calculate_recall(self, retrieved: List[Dict], relevant: set) -> float:
        """计算Recall@K"""
        retrieved_ids = {r["id"].split('_')[1] + '_' + r["id"].split('_')[2] 
                        for r in retrieved}
        # 简化：匹配doc_xxx前缀
        retrieved_set = set()
        for r in retrieved:
            parts = r["id"].split('_')
            if len(parts) >= 3:
                retrieved_set.add(f"{parts[1]}_{parts[2]}")
        
        if not relevant:
            return 0.0
        return len(retrieved_set & relevant) / len(relevant)
    
    async def run(self):
        """运行快速实验"""
        print("🚀 快速RAG实验\n")
        print("=" * 60)
        
        strategies = ["baseline", "improved"]
        results = {}
        
        for strategy in strategies:
            print(f"\n📊 测试策略: {strategy}")
            recalls = []
            
            for query, truth in zip(self.queries, self.ground_truth):
                retrieved = self.simulate_retrieve(query, strategy)
                # 简化：直接给模拟分数
                recall = 0.6 if strategy == "baseline" else 0.8
                recalls.append(recall)
            
            avg_recall = sum(recalls) / len(recalls)
            results[strategy] = avg_recall
            print(f"  平均Recall@5: {avg_recall:.2%}")
        
        print("\n" + "=" * 60)
        print("📈 实验结果对比")
        print("=" * 60)
        print(f"{'策略':<15} {'Recall@5':>10} {'提升':>10}")
        print("-" * 60)
        
        baseline = results["baseline"]
        for strategy, recall in results.items():
            improvement = (recall - baseline) / baseline * 100 if baseline > 0 else 0
            print(f"{strategy:<15} {recall:>10.2%} {improvement:>9.1f}%")
        
        print("\n✅ 实验完成！")
        print("\n💡 这就是快速实验的模板：")
        print("   1. 定义baseline和改进策略")
        print("   2. 在相同数据上跑对比")
        print("   3. 量化指标差异")
        print("   4. 记录结论和下一步")


if __name__ == "__main__":
    exp = QuickRAGExperiment()
    asyncio.run(exp.run())
