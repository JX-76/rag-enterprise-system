#!/usr/bin/env python3
"""
文本可视化 - 无需matplotlib
生成ASCII图表和表格

用法:
    python scripts/text_visualize.py --input experiments/*.json
"""
import argparse
import json
from pathlib import Path
from typing import List, Dict


def print_bar_chart(values: List[float], labels: List[str], title: str, width: int = 50):
    """打印ASCII柱状图"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")
    
    if not values:
        print("  无数据")
        return
    
    max_val = max(values) if max(values) > 0 else 1
    max_label_len = max(len(str(l)) for l in labels)
    
    for label, value in zip(labels, values):
        bar_len = int((value / max_val) * width)
        bar = '█' * bar_len
        percentage = value * 100 if value <= 1 else value
        unit = '%' if value <= 1 else ''
        print(f"  {str(label):<{max_label_len}} |{bar:<{width}}| {value:.3f}{unit}")
    
    print(f"{'='*60}\n")


def print_comparison_table(results: List[Dict], title: str):
    """打印对比表格"""
    print(f"\n{'='*80}")
    print(f"  {title}")
    print(f"{'='*80}")
    
    if not results:
        print("  无数据")
        return
    
    # 表头
    print(f"  {'Variant':<20} {'Recall@5':>10} {'MRR':>10} {'NDCG@5':>10} {'Latency':>12}")
    print(f"  {'-'*78}")
    
    # 找出最佳值
    best_recall = max(r['metrics'].get('recall@5', 0) for r in results)
    
    # 数据行
    for r in results:
        m = r['metrics']
        variant = r['variant']
        recall = m.get('recall@5', 0)
        mrr = m.get('mrr', 0)
        ndcg = m.get('ndcg@5', 0)
        latency = m.get('latency_ms', 0)
        
        marker = " 🏆" if recall == best_recall else ""
        print(f"  {variant:<20} {recall:>10.3f} {mrr:>10.3f} {ndcg:>10.3f} {latency:>10.1f}ms{marker}")
    
    print(f"{'='*80}\n")


def print_summary(experiments: List[Dict]):
    """打印实验摘要"""
    print("\n" + "="*80)
    print("  RAG EXPERIMENTS SUMMARY")
    print("="*80)
    
    for exp in experiments:
        print(f"\n  📊 {exp.get('name', 'Unknown')}")
        print(f"     {exp.get('description', '')}")
        print(f"     Time: {exp.get('timestamp', 'N/A')}")
        
        results = exp.get('results', [])
        if results:
            best = max(results, key=lambda x: x['metrics'].get('recall@5', 0))
            print(f"     🏆 Best: {best['variant']} (Recall@5={best['metrics']['recall@5']:.3f})")


def visualize_experiment(exp: Dict):
    """可视化单个实验"""
    results = exp.get('results', [])
    if not results:
        return
    
    exp_name = exp.get('name', 'Experiment')
    
    # 提取数据
    variants = [r['variant'] for r in results]
    recall = [r['metrics'].get('recall@5', 0) for r in results]
    mrr = [r['metrics'].get('mrr', 0) for r in results]
    latency = [r['metrics'].get('latency_ms', 0) for r in results]
    
    # 打印表格
    print_comparison_table(results, exp_name)
    
    # 打印柱状图
    print_bar_chart(recall, variants, "Recall@5 Comparison")
    print_bar_chart(mrr, variants, "MRR Comparison")
    print_bar_chart(latency, variants, "Latency Comparison (ms)")


def main():
    parser = argparse.ArgumentParser(description="Text Visualization for Experiments")
    parser.add_argument("--input", nargs='+', required=True, help="Experiment JSON files")
    
    args = parser.parse_args()
    
    # 加载实验
    experiments = []
    for file in args.input:
        path = Path(file)
        if path.exists():
            with open(path, 'r', encoding='utf-8') as f:
                experiments.append(json.load(f))
        else:
            print(f"⚠️ 文件不存在: {file}")
    
    if not experiments:
        print("❌ 没有找到实验文件")
        return
    
    # 打印摘要
    print_summary(experiments)
    
    # 可视化每个实验
    for exp in experiments:
        visualize_experiment(exp)
    
    print("\n" + "="*80)
    print("  可视化完成！")
    print("="*80)


if __name__ == "__main__":
    main()
