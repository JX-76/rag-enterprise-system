# RAG Demo - Dockerfile
# 基于 Python 3.11 轻量镜像

FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目代码
COPY src/ ./src/
COPY main.py .
COPY config.py .

# 创建数据目录
RUN mkdir -p /app/data/uploads

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["python", "main.py"]

# 构建说明：
# docker build -t rag-demo .
# 
# 运行说明（本地）：
# docker run -p 8000:8000 -v $(pwd)/data:/app/data rag-demo
