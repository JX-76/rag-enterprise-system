#!/bin/bash
# RAG Enterprise System - 本地部署脚本

set -e

echo "🚀 RAG Enterprise System 本地部署"
echo "=================================="

# 检查Python版本
PYTHON_VERSION=$(python3 --version 2>&1 | grep -oP '\d+\.\d+')
REQUIRED_VERSION="3.9"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    echo "❌ Python版本过低，需要 >= 3.9，当前: $PYTHON_VERSION"
    exit 1
fi

echo "✅ Python版本检查通过: $PYTHON_VERSION"

# 创建虚拟环境
if [ ! -d "venv" ]; then
    echo "📦 创建虚拟环境..."
    python3 -m venv venv
fi

echo "📦 激活虚拟环境..."
source venv/bin/activate

# 升级pip
echo "📦 升级pip..."
pip install --upgrade pip

# 安装依赖
echo "📦 安装依赖..."
pip install -r requirements.txt

# 创建必要目录
echo "📁 创建数据目录..."
mkdir -p data/chroma
mkdir -p data/milvus
mkdir -p logs
mkdir -p models

echo "✅ 环境准备完成！"
echo ""
echo "📝 下一步:"
echo "   1. 复制环境变量: cp .env.example .env"
echo "   2. 编辑.env配置你的API密钥"
echo "   3. 运行: python examples/integrated_rag_demo.py"
