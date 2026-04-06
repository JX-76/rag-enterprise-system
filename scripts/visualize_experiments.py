#!/usr/bin/env python3
"""
实验结果可视化脚本
生成图表用于报告和展示

用法:
    python scripts/visualize_experiments.py --input experiments/chunk_size_*.json --output reports/
    python scripts/visualize_experiments.py --all --output reports/
"""
import argparse
import json
import matplotlib
matplotlib.use('Agg')  # 无GUI环境
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
from typing import List, Dict, Any
from collections import defaultdict


class ExperimentVisualizer:
    """实验结果可视化器"""
    
    def __init__(self, output_dir: str = "reports"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # 设置中文字体
        plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial Unicode MS', 'SimHei']
        plt.rcParams['axes.unicode_minus'] = False
    
    def load_experiments(self, pattern: str) -> List[Dict]:
        """加载实验结果文件"""
        experiments = []
        
        if pattern == "--all":
            # 加载所有实验
            exp_dir = Path("experiments")
            if exp_dir.exists():
                files = list(exp_dir.glob("*.json"))
            else:
                files = []
        else:
            # 加载指定文件
            import glob
            files = [Path(f) for f in glob.glob(pattern)]
        
        for file in files:
            try:
                with open(file, 'r', encoding='utf-8') as f:
                    exp = json.load(f)
                    exp['file'] = file.name
                    experiments.append(exp)
            except Exception as e:
                print(f"⚠️ 加载失败 {file}: {e}")
        
        return experiments
    
    def plot_experiment_comparison(self, experiments: List[Dict], metric: str = "recall@5"):
        """
        对比不同实验的结果
        
        Args:
            experiments: 实验结果列表
            metric: 要对比的指标
        """
        fig, ax = plt.subplots(figsize=(12, 6))
        
        colors = ['#2E86AB', '#A23B72', '#F18F01', '#C73E1D', '#6A994E']
        
        for idx, exp in enumerate(experiments):
            exp_name = exp.get('name', f"Exp {idx+1}")
            results = exp.get('results', [])
            
            if not results:
                continue
            
            variants = [r['variant'] for r in results]
            values = [r['metrics'].get(metric, 0) for r in results]
            
            x = np.arange(len(variants))
            width = 0.15
            offset = (idx - len(experiments)/2) * width
            
            bars = ax.bar(x + offset, values, width, label=exp_name, color=colors[idx % len(colors)])
            
            # 在柱子上显示数值
            for bar in bars:
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height,
                       f'{height:.3f}',
                       ha='center', va='bottom', fontsize=8)
        
        ax.set_xlabel('Variant', fontsize=12)
        ax.set_ylabel(metric.upper(), fontsize=12)
        ax.set_title(f'Experiment Comparison - {metric.upper()}', fontsize=14, fontweight='bold')
        ax.set_xticks(x)
        ax.set_xticklabels(variants, rotation=45, ha='right')
        ax.legend()
        ax.grid(axis='y', alpha=0.3)
        
        plt.tight_layout()
        
        output_file = self.output_dir / f"comparison_{metric}.png"
        plt.savefig(output_file, dpi=150, bbox_inches='tight')
        plt.close()
        
        print(f"✅ 图表已保存: {output_file}")
        return output_file
    
    def plot_single_experiment(self, exp: Dict):
        """绘制单个实验的详细结果"""
        exp_name = exp.get('name', 'Unknown')
        results = exp.get('results', [])
        
        if not results:
            print(f"⚠️ 实验 {exp_name} 没有结果")
            return
        
        # 提取数据
        variants = [r['variant'] for r in results]
        recall_5 = [r['metrics'].get('recall@5', 0) for r in results]
        mrr = [r['metrics'].get('mrr', 0) for r in results]
        ndcg = [r['metrics'].get('ndcg@5', 0) for r in results]
        latency = [r['metrics'].get('latency_ms', 0) for r in results]
        
        # 创建子图
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        fig.suptitle(f'Experiment: {exp_name}', fontsize=16, fontweight='bold')
        
        # Recall@5
        ax = axes[0, 0]
        bars = ax.bar(variants, recall_5, color='#2E86AB')
        ax.set_ylabel('Recall@5')
        ax.set_ylim(0, 1)
        ax.grid(axis='y', alpha=0.3)
        for bar, val in zip(bars, recall_5):
            ax.text(bar.get_x() + bar.get_width()/2., bar.get_height(),
                   f'{val:.3f}', ha='center', va='bottom', fontsize=9)
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')
        
        # MRR
        ax = axes[0, 1]
        bars = ax.bar(variants, mrr, color='#A23B72')
        ax.set_ylabel('MRR')
        ax.set_ylim(0, 1)
        ax.grid(axis='y', alpha=0.3)
        for bar, val in zip(bars, mrr):
            ax.text(bar.get_x() + bar.get_width()/2., bar.get_height(),
                   f'{val:.3f}', ha='center', va='bottom', fontsize=9)
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')
        
        # NDCG@5
        ax = axes[1, 0]
        bars = ax.bar(variants, ndcg, color='#F18F01')
        ax.set_ylabel('NDCG@5')
        ax.set_ylim(0, 1)
        ax.grid(axis='y', alpha=0.3)
        for bar, val in zip(bars, ndcg):
            ax.text(bar.get_x() + bar.get_width()/2., bar.get_height(),
                   f'{val:.3f}', ha='center', va='bottom', fontsize=9)
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')
        
        # Latency
        ax = axes[1, 1]
        bars = ax.bar(variants, latency, color='#6A994E')
        ax.set_ylabel('Latency (ms)')
        ax.grid(axis='y', alpha=0.3)
        for bar, val in zip(bars, latency):
            ax.text(bar.get_x() + bar.get_width()/2., bar.get_height(),
                   f'{val:.1f}', ha='center', va='bottom', fontsize=9)
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')
        
        plt.tight_layout()
        
        exp_key = exp.get('experiment', 'unknown')
        output_file = self.output_dir / f"{exp_key}_details.png"
        plt.savefig(output_file, dpi=150, bbox_inches='tight')
        plt.close()
        
        print(f"✅ 图表已保存: {output_file}")
        return output_file
    
    def plot_metrics_radar(self, experiments: List[Dict]):
        """绘制雷达图对比多个实验"""
        if len(experiments) < 2:
            print("⚠️ 需要至少2个实验来绘制雷达图")
            return
        
        # 选择第一个实验的各variant进行对比
        fig, axes = plt.subplots(1, len(experiments), figsize=(6*len(experiments), 6),
                                subplot_kw=dict(projection='polar'))
        
        if len(experiments) == 1:
            axes = [axes]
        
        metrics = ['recall@5', 'mrr', 'ndcg@5']
        angles = np.linspace(0, 2*np.pi, len(metrics), endpoint=False).tolist()
        angles += angles[:1]  # 闭合
        
        for ax, exp in zip(axes, experiments):
            results = exp.get('results', [])
            if not results:
                continue
            
            for r in results:
                values = [r['metrics'].get(m, 0) for m in metrics]
                values += values[:1]  # 闭合
                
                ax.plot(angles, values, 'o-', linewidth=2, label=r['variant'])
                ax.fill(angles, values, alpha=0.15)
            
            ax.set_xticks(angles[:-1])
            ax.set_xticklabels(metrics)
            ax.set_ylim(0, 1)
            ax.set_title(exp.get('name', ''), fontsize=12, fontweight='bold')
            ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.0))
        
        plt.tight_layout()
        
        output_file = self.output_dir / "metrics_radar.png"
        plt.savefig(output_file, dpi=150, bbox_inches='tight')
        plt.close()
        
        print(f"✅ 雷达图已保存: {output_file}")
        return output_file
    
    def generate_html_report(self, experiments: List[Dict]):
        """生成HTML报告"""
        html = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>RAG Experiments Report</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 1200px; margin: 0 auto; padding: 20px; }
        h1 { color: #2E86AB; border-bottom: 3px solid #2E86AB; padding-bottom: 10px; }
        h2 { color: #A23B72; margin-top: 30px; }
        .experiment { background: #f5f5f5; padding: 20px; margin: 20px 0; border-radius: 8px; }
        .metric { display: inline-block; margin: 10px 20px 10px 0; padding: 10px 15px; background: white; border-radius: 5px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .metric-value { font-size: 24px; font-weight: bold; color: #2E86AB; }
        .metric-label { font-size: 12px; color: #666; }
        .winner { background: #d4edda; border: 2px solid #28a745; }
        table { width: 100%; border-collapse: collapse; margin: 20px 0; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background: #2E86AB; color: white; }
        tr:hover { background: #f5f5f5; }
        .timestamp { color: #999; font-size: 12px; }
    </style>
</head>
<body>
    <h1>🔬 RAG System Experiments Report</h1>
    <p class="timestamp">Generated: {}</p>
""".format(__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        
        for exp in experiments:
            html += f"""
    <div class="experiment">
        <h2>{exp.get('name', 'Unknown Experiment')}</h2>
        <p>{exp.get('description', '')}</p>
        <p class="timestamp">Timestamp: {exp.get('timestamp', 'N/A')}</p>
        
        <table>
            <tr>
                <th>Variant</th>
                <th>Recall@5</th>
                <th>MRR</th>
                <th>NDCG@5</th>
                <th>Latency</th>
            </tr>
"""
            
            # 找出最佳结果
            results = exp.get('results', [])
            if results:
                best_recall = max(r['metrics'].get('recall@5', 0) for r in results)
            else:
                best_recall = 0
            
            for r in results:
                m = r['metrics']
                is_winner = m.get('recall@5', 0) == best_recall
                row_class = 'winner' if is_winner else ''
                
                html += f"""
            <tr class="{row_class}">
                <td><strong>{r['variant']}</strong></td>
                <td>{m.get('recall@5', 0):.3f}</td>
                <td>{m.get('mrr', 0):.3f}</td>
                <td>{m.get('ndcg@5', 0):.3f}</td>
                <td>{m.get('latency_ms', 0):.1f}ms</td>
            </tr>
"""
            
            html += """
        </table>
    </div>
"""
        
        html += """
</body>
</html>
"""
        
        output_file = self.output_dir / "report.html"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html)
        
        print(f"✅ HTML报告已保存: {output_file}")
        return output_file


def main():
    parser = argparse.ArgumentParser(description="Visualize RAG Experiments")
    parser.add_argument("--input", default="--all", help="Input pattern or '--all'")
    parser.add_argument("--output", default="reports", help="Output directory")
    parser.add_argument("--format", choices=["png", "html", "all"], default="all",
                       help="Output format")
    
    args = parser.parse_args()
    
    visualizer = ExperimentVisualizer(output_dir=args.output_dir)
    
    # 加载实验
    experiments = visualizer.load_experiments(args.input)
    
    if not experiments:
        print("❌ 没有找到实验结果文件")
        print("提示: 先运行 python scripts/run_experiments.py")
        return
    
    print(f"📊 加载了 {len(experiments)} 个实验")
    
    # 生成图表
    if args.format in ["png", "all"]:
        # 单个实验详细图
        for exp in experiments:
            visualizer.plot_single_experiment(exp)
        
        # 对比图
        if len(experiments) > 1:
            visualizer.plot_experiment_comparison(experiments, metric="recall@5")
            visualizer.plot_experiment_comparison(experiments, metric="mrr")
        
        # 雷达图
        visualizer.plot_metrics_radar(experiments)
    
    # 生成HTML报告
    if args.format in ["html", "all"]:
        visualizer.generate_html_report(experiments)
    
    print(f"\n✅ 所有可视化完成！输出目录: {args.output_dir}")


if __name__ == "__main__":
    main()
