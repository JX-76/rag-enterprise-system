#!/usr/bin/env python3
"""Debug metrics module"""
import sys
import os
import importlib.util

spec = importlib.util.spec_from_file_location(
    "metrics",
    os.path.join(os.path.dirname(__file__), "src/evaluation/metrics.py")
)
module = importlib.util.module_from_spec(spec)
sys.modules["metrics"] = module
spec.loader.exec_module(module)

RetrievalEvaluator = module.RetrievalEvaluator

queries = ["q1", "q2"]
retrieved = [[("doc1", 0.9)], [("doc2", 0.8)]]
ground_truth = [{"doc1"}, {"doc2"}]

evaluator = RetrievalEvaluator()
try:
    metrics = evaluator.evaluate(queries, retrieved, ground_truth)
    print(f"Success! Type: {type(metrics)}")
    print(f"Value: {metrics}")
    print(f"Has recall_at_k: {hasattr(metrics, 'recall_at_k')}")
    if hasattr(metrics, 'recall_at_k'):
        print(f"recall_at_k: {metrics.recall_at_k}")
except Exception as e:
    import traceback
    print(f"Error: {e}")
    traceback.print_exc()
