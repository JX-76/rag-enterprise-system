#!/usr/bin/env python3
"""向量化服务测试（Mock版本，无依赖）"""
import sys
import os
import importlib.util

# 直接导入，避免级联依赖
spec = importlib.util.spec_from_file_location(
    "embedding_service",
    os.path.join(os.path.dirname(__file__), "src/services/embedding_service.py")
)
module = importlib.util.module_from_spec(spec)
sys.modules["embedding_service"] = module
spec.loader.exec_module(module)

EmbeddingService = module.EmbeddingService
VectorStore = module.VectorStore
EmbeddingConfig = module.EmbeddingConfig
VectorStoreConfig = module.VectorStoreConfig

print("="*60)
print("向量化服务测试")
print("="*60)

# 检查依赖
print("\n依赖检查:")
print(f"  torch/transformers: {module.TORCH_AVAILABLE}")
print(f"  chromadb: {module.CHROMA_AVAILABLE}")

# 测试EmbeddingService（依赖未安装时跳过）
if module.TORCH_AVAILABLE:
    print("\n✅ 依赖已安装，测试向量化...")
    
    service = EmbeddingService(EmbeddingConfig(
        model_name="BAAI/bge-small-zh-v1.5",
        device="cpu"
    ))
    
    print(f"\n模型信息: {service.get_model_info()}")
    
    # 测试编码
    texts = ["机器学习是人工智能的一个分支", "深度学习使用神经网络"]
    embeddings = service.encode(texts)
    
    print(f"\n编码测试:")
    print(f"  输入: {texts}")
    print(f"  输出维度: {len(embeddings[0])}")
    print(f"  向量数: {len(embeddings)}")
    
    # 测试相似度
    sim = service.similarity(embeddings[0], embeddings[1:])
    print(f"  相似度: {sim}")
else:
    print("\n⚠️ 依赖未安装，跳过向量化测试")
    print("  安装: pip install torch sentence-transformers")

# 测试VectorStore（依赖未安装时跳过）
if module.CHROMA_AVAILABLE:
    print("\n✅ ChromaDB已安装，测试向量存储...")
    
    store = VectorStore(VectorStoreConfig(
        persist_directory="/tmp/test_chroma",
        collection_name="test"
    ))
    
    # 添加文档（使用模拟向量）
    docs = [
        {"id": "1", "text": "机器学习简介", "metadata": {"source": "test"}},
        {"id": "2", "text": "深度学习原理", "metadata": {"source": "test"}},
    ]
    embeddings = [[0.1]*384, [0.2]*384]  # 模拟向量
    
    store.add_documents(docs, embeddings)
    print(f"\n存储统计: {store.get_stats()}")
    
    # 搜索
    results = store.search([0.15]*384, top_k=2)
    print(f"\n搜索结果:")
    for r in results:
        print(f"  {r['id']}: {r['text']} (score: {r['score']:.4f})")
else:
    print("\n⚠️ ChromaDB未安装，跳过存储测试")
    print("  安装: pip install chromadb")

print("\n" + "="*60)
print("✅ 测试完成!")
print("="*60)
