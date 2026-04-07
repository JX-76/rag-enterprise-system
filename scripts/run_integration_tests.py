#!/usr/bin/env python3
"""
集成测试套件 - 端到端验证

测试覆盖:
1. 文档入库流程
2. 查询检索流程
3. 多轮对话 + Memory
4. 性能基准
"""
import sys
import time
import json
import tempfile
import os
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rag.pipeline import DefaultRAGPipeline, RAGConfig
from memory import MemoryManager


class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'


def print_header(text):
    print(f"\n{Colors.BLUE}{'='*60}{Colors.END}")
    print(f"{Colors.BLUE}{text}{Colors.END}")
    print(f"{Colors.BLUE}{'='*60}{Colors.END}")


def print_success(text):
    print(f"{Colors.GREEN}✓ {text}{Colors.END}")


def print_error(text):
    print(f"{Colors.RED}✗ {text}{Colors.END}")


def print_warning(text):
    print(f"{Colors.YELLOW}⚠ {text}{Colors.END}")


class IntegrationTestSuite:
    """集成测试套件"""
    
    def __init__(self):
        self.results = []
        self.pipeline = None
        
    def setup(self):
        """测试环境准备"""
        print_header("测试环境准备")
        
        config = RAGConfig(
            chunk_size=300,
            chunk_overlap=50,
            top_k=5
        )
        
        try:
            self.pipeline = DefaultRAGPipeline(config)
            print_success("RAG Pipeline 初始化成功")
            return True
        except Exception as e:
            print_error(f"Pipeline 初始化失败: {e}")
            return False
    
    def test_document_ingestion(self):
        """测试文档入库流程"""
        print_header("测试1: 文档入库流程")
        
        # 创建测试文档
        test_docs = [
            ("doc1.txt", "RAG技术是一种将检索和生成结合的AI方法。"),
            ("doc2.txt", "向量数据库用于存储高维向量，支持相似度检索。"),
            ("doc3.txt", "大语言模型可以理解和生成自然语言文本。"),
        ]
        
        doc_paths = []
        for filename, content in test_docs:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', 
                                             delete=False, encoding='utf-8') as f:
                f.write(content)
                doc_paths.append(f.name)
        
        try:
            # 批量入库
            start_time = time.time()
            results = self.pipeline.ingest_documents(doc_paths, show_progress=False)
            elapsed = time.time() - start_time
            
            # 验证结果
            success_count = sum(1 for r in results if r.success)
            
            if success_count == len(test_docs):
                print_success(f"文档入库成功: {success_count}/{len(test_docs)}")
                print_success(f"入库耗时: {elapsed:.2f}s")
                self.results.append(("文档入库", True, elapsed))
                return True
            else:
                print_error(f"部分文档入库失败: {success_count}/{len(test_docs)}")
                self.results.append(("文档入库", False, elapsed))
                return False
                
        except Exception as e:
            print_error(f"文档入库异常: {e}")
            self.results.append(("文档入库", False, 0))
            return False
        finally:
            # 清理
            for path in doc_paths:
                os.unlink(path)
    
    def test_query_retrieval(self):
        """测试查询检索流程"""
        print_header("测试2: 查询检索流程")
        
        queries = [
            "什么是RAG？",
            "向量数据库有什么用？",
            "大语言模型能做什么？",
        ]
        
        all_passed = True
        times = []
        
        for query in queries:
            try:
                start_time = time.time()
                result = self.pipeline.query(query)
                elapsed = time.time() - start_time
                times.append(elapsed)
                
                if result.answer and len(result.retrieved_docs) > 0:
                    print_success(f"'{query[:20]}...' 检索成功 ({elapsed:.3f}s)")
                else:
                    print_warning(f"'{query[:20]}...' 检索结果为空")
                    all_passed = False
                    
            except Exception as e:
                print_error(f"'{query[:20]}...' 检索失败: {e}")
                all_passed = False
        
        avg_time = sum(times) / len(times) if times else 0
        print_success(f"平均检索耗时: {avg_time:.3f}s")
        
        self.results.append(("查询检索", all_passed, avg_time))
        return all_passed
    
    def test_multi_turn_conversation(self):
        """测试多轮对话 + Memory"""
        print_header("测试3: 多轮对话 + Memory")
        
        session_id = "test_session_integration"
        user_id = "test_user"
        
        conversation = [
            ("user", "什么是RAG技术？"),
            ("assistant", "RAG是检索增强生成技术。"),
            ("user", "它有什么优势？"),  # 代词"它"应该被理解
        ]
        
        all_passed = True
        times = []
        
        for i, (role, content) in enumerate(conversation):
            try:
                start_time = time.time()
                
                if role == "user":
                    result = self.pipeline.chat(
                        query=content,
                        session_id=session_id,
                        user_id=user_id,
                        use_memory=True
                    )
                    
                    # 验证记忆使用
                    history_used = result.metadata.get("history_used", False)
                    elapsed = time.time() - start_time
                    times.append(elapsed)
                    
                    if i == 0:
                        print_success(f"第1轮对话成功 ({elapsed:.3f}s)")
                    elif i == 2:
                        # 第3轮应该使用了历史
                        if history_used:
                            print_success(f"第2轮对话成功，使用了历史记忆 ({elapsed:.3f}s)")
                        else:
                            print_warning(f"第2轮对话成功，但未使用历史记忆")
                            
            except Exception as e:
                print_error(f"第{i+1}轮对话失败: {e}")
                all_passed = False
        
        # 验证记忆统计
        try:
            stats = self.pipeline.get_memory_stats(user_id)
            ultra_count = stats.get("ultra_short_memory_count", 0)
            print_success(f"记忆统计: 超短期记忆 {ultra_count} 条")
        except Exception as e:
            print_warning(f"记忆统计获取失败: {e}")
        
        avg_time = sum(times) / len(times) if times else 0
        self.results.append(("多轮对话", all_passed, avg_time))
        return all_passed
    
    def test_performance_baseline(self):
        """测试性能基准"""
        print_header("测试4: 性能基准")
        
        # 快速响应测试
        query = "什么是RAG？"
        
        # 预热
        for _ in range(3):
            self.pipeline.query(query)
        
        # 正式测试
        times = []
        for _ in range(10):
            start = time.time()
            result = self.pipeline.query(query)
            times.append(time.time() - start)
        
        avg_time = sum(times) / len(times)
        min_time = min(times)
        max_time = max(times)
        
        print_success(f"平均响应时间: {avg_time*1000:.1f}ms")
        print_success(f"最小响应时间: {min_time*1000:.1f}ms")
        print_success(f"最大响应时间: {max_time*1000:.1f}ms")
        
        # 性能阈值检查 (500ms)
        passed = avg_time < 0.5
        if passed:
            print_success("性能满足 <500ms 阈值")
        else:
            print_error(f"性能未达标: {avg_time*1000:.1f}ms > 500ms")
        
        self.results.append(("性能基准", passed, avg_time))
        return passed
    
    def generate_report(self):
        """生成测试报告"""
        print_header("测试报告")
        
        passed = sum(1 for _, success, _ in self.results if success)
        total = len(self.results)
        
        print(f"\n总计: {passed}/{total} 通过")
        print()
        
        for name, success, metric in self.results:
            symbol = "✓" if success else "✗"
            color = Colors.GREEN if success else Colors.RED
            unit = "s" if "时间" in name or "耗时" in name else ""
            print(f"  {color}[{symbol}]{Colors.END} {name}: {metric:.3f}{unit}")
        
        # 保存JSON报告
        report = {
            "timestamp": datetime.now().isoformat(),
            "total_tests": total,
            "passed": passed,
            "failed": total - passed,
            "results": [
                {"name": name, "success": success, "metric": metric}
                for name, success, metric in self.results
            ]
        }
        
        report_path = Path("test_reports")
        report_path.mkdir(exist_ok=True)
        
        json_path = report_path / f"integration_test_{datetime.now():%Y%m%d_%H%M%S}.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        print(f"\n报告已保存: {json_path}")
        
        return passed == total
    
    def run_all(self):
        """运行所有测试"""
        print_header("RAG Enterprise System - 集成测试套件")
        print(f"开始时间: {datetime.now():%Y-%m-%d %H:%M:%S}")
        print()
        
        if not self.setup():
            print_error("环境准备失败，测试终止")
            return False
        
        # 运行测试
        self.test_document_ingestion()
        self.test_query_retrieval()
        self.test_multi_turn_conversation()
        self.test_performance_baseline()
        
        # 生成报告
        all_passed = self.generate_report()
        
        print_header("测试完成")
        if all_passed:
            print(f"{Colors.GREEN}🎉 所有测试通过！{Colors.END}")
        else:
            print(f"{Colors.RED}⚠️ 部分测试失败，请检查。{Colors.END}")
        
        return all_passed


def main():
    suite = IntegrationTestSuite()
    success = suite.run_all()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
