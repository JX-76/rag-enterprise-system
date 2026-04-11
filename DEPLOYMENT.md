# 部署指南 - Deployment Guide

本文档提供详细的部署说明，涵盖开发环境、测试环境和生产环境。

---

## 📋 目录

1. [环境要求](#环境要求)
2. [开发环境部署](#开发环境部署)
3. [测试环境部署](#测试环境部署)
4. [生产环境部署](#生产环境部署)
5. [Docker部署](#docker部署)
6. [Kubernetes部署](#kubernetes部署)
7. [监控与日志](#监控与日志)
8. [常见问题](#常见问题)

---

## 环境要求

### 最低配置

| 组件 | 最低配置 | 推荐配置 |
|------|---------|---------|
| CPU | 4核 | 8核+ |
| 内存 | 8GB | 16GB+ |
| 存储 | 50GB SSD | 100GB SSD |
| GPU | 可选 | NVIDIA RTX 4090 / A100 |
| 网络 | 10Mbps | 100Mbps+ |

### 软件依赖

```bash
# 必须
Python >= 3.9
Git

# 可选但推荐
Docker >= 20.10
Docker Compose >= 2.0
NVIDIA Docker (如使用GPU)
```

### 外部服务依赖

| 服务 | 用途 | 是否必须 | 自建/云厂商 |
|------|------|---------|------------|
| 向量数据库 | 文档存储与检索 | 是 | Milvus/Chroma/Pinecone |
| 缓存服务 | 查询缓存 | 推荐 | Redis/Valkey |
| 对象存储 | 文件存储 | 可选 | MinIO/S3/OSS |
| LLM API | 文本生成 | 是 | OpenAI/Claude/本地模型 |
| Embedding服务 | 向量化 | 是 | BGE/OpenAI/local |

---

## 开发环境部署

### 步骤1: 克隆代码

```bash
git clone https://github.com/JX-76/rag-enterprise-system.git
cd rag-enterprise-system
```

### 步骤2: 创建虚拟环境

```bash
# 使用venv
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows

# 或使用conda
conda create -n rag python=3.11
conda activate rag
```

### 步骤3: 安装依赖

```bash
# 基础依赖
pip install -r requirements.txt

# 开发依赖（可选）
pip install -r requirements-dev.txt
```

### 步骤4: 配置环境变量

```bash
# 复制示例配置
cp .env.example .env

# 编辑配置
vim .env
```

**必需配置项:**

```env
# API密钥（至少配置一个）
OPENAI_API_KEY=sk-your-openai-key
# 或
ANTHROPIC_API_KEY=sk-your-anthropic-key

# 向量数据库
VECTOR_STORE_TYPE=chroma  # 或 milvus, pinecone
CHROMA_PERSIST_DIR=./data/chroma

# 缓存
REDIS_URL=redis://localhost:6379/0

# 应用配置
APP_ENV=development
LOG_LEVEL=DEBUG
```

### 步骤5: 验证安装

```bash
# 运行测试
python test_all.py

# 运行快速演示
python examples/demo_quickstart.py

# 启动开发服务器
make run
# 或
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

### 步骤6: 验证服务

```bash
# 健康检查
curl http://localhost:8000/api/v1/health

# 查看API文档
open http://localhost:8000/docs
```

---

## 测试环境部署

### 使用Docker Compose（推荐）

```bash
# 1. 配置环境
cp .env.example .env
# 编辑 .env，设置 APP_ENV=staging

# 2. 启动所有服务
docker-compose up -d

# 3. 查看状态
docker-compose ps

# 4. 查看日志
docker-compose logs -f api
```

### 服务组成

```yaml
# docker-compose.yml 包含:
api:        # RAG API服务
redis:      # 缓存服务
milvus:     # 向量数据库 (可选)
prometheus: # 监控指标
grafana:    # 可视化面板
```

### 端口映射

| 服务 | 端口 | 说明 |
|------|------|------|
| API | 8000 | 主服务接口 |
| Redis | 6379 | 缓存服务 |
| Milvus | 19530 | 向量数据库 |
| Prometheus | 9090 | 指标收集 |
| Grafana | 3000 | 监控面板 |

---

## 生产环境部署

### 架构图

```
                    ┌─────────────┐
                    │   Nginx     │
                    │   (LB)      │
                    └──────┬──────┘
                           │
           ┌───────────────┼───────────────┐
           │               │               │
      ┌────▼────┐     ┌────▼────┐     ┌────▼────┐
      │  API-1  │     │  API-2  │     │  API-3  │
      └────┬────┘     └────┬────┘     └────┬────┘
           │               │               │
           └───────────────┼───────────────┘
                           │
      ┌────────────────────┼────────────────────┐
      │                    │                    │
┌─────▼─────┐      ┌───────▼────────┐   ┌──────▼─────┐
│   Redis   │      │     Milvus     │   │ Prometheus │
│  (集群)   │      │   (分布式)      │   │  + Grafana │
└───────────┘      └────────────────┘   └────────────┘
```

### 部署步骤

#### 1. 准备服务器

```bash
# 系统要求
Ubuntu 22.04 LTS / CentOS 8
Docker 24.0+
Docker Compose 2.20+

# 安装Docker
curl -fsSL https://get.docker.com | sh

# 安装Nginx
apt-get update
apt-get install -y nginx
```

#### 2. 配置Nginx

```nginx
# /etc/nginx/sites-available/rag
upstream rag_backend {
    least_conn;
    server 127.0.0.1:8001;
    server 127.0.0.1:8002;
    server 127.0.0.1:8003;
}

server {
    listen 80;
    server_name api.yourdomain.com;

    location / {
        proxy_pass http://rag_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

#### 3. 生产环境配置

```env
# .env.production
APP_ENV=production
DEBUG=false
LOG_LEVEL=INFO

# API密钥
OPENAI_API_KEY=sk-your-production-key

# 向量数据库（生产集群）
VECTOR_STORE_TYPE=milvus
MILVUS_HOST=milvus-cluster.internal
MILVUS_PORT=19530

# Redis集群
REDIS_URL=redis://redis-cluster.internal:6379/0

# 限流配置
RATE_LIMIT_RPM=1000
RATE_LIMIT_BURST=1500

# 熔断配置
CIRCUIT_FAILURE_THRESHOLD=5
CIRCUIT_RECOVERY_TIMEOUT=30

# 监控
PROMETHEUS_ENABLED=true
METRICS_PORT=9090
```

#### 4. 启动服务

```bash
# 使用生产配置
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# 或手动启动多个实例
docker run -d -p 8001:8000 \
  --env-file .env.production \
  --name rag-api-1 \
  rag-enterprise-system:latest

docker run -d -p 8002:8000 \
  --env-file .env.production \
  --name rag-api-2 \
  rag-enterprise-system:latest

docker run -d -p 8003:8000 \
  --env-file .env.production \
  --name rag-api-3 \
  rag-enterprise-system:latest
```

#### 5. 健康检查

```bash
# 检查所有实例
for port in 8001 8002 8003; do
  curl -f http://localhost:$port/api/v1/health || echo "Instance on $port failed"
done

# 检查负载均衡
curl http://localhost/api/v1/health
```

---

## Docker部署

### 构建镜像

```bash
# 构建
docker build -t rag-enterprise-system:latest .

# 标记版本
docker tag rag-enterprise-system:latest rag-enterprise-system:v1.0.0
```

### 运行容器

```bash
# 基础运行
docker run -d \
  -p 8000:8000 \
  -e OPENAI_API_KEY=sk-your-key \
  -v $(pwd)/data:/app/data \
  --name rag-api \
  rag-enterprise-system:latest

# 带GPU支持
docker run -d \
  --gpus all \
  -p 8000:8000 \
  --name rag-api-gpu \
  rag-enterprise-system:latest
```

### Docker Compose配置

```yaml
version: '3.8'

services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - APP_ENV=production
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - VECTOR_STORE_TYPE=milvus
      - MILVUS_HOST=milvus
    depends_on:
      - redis
      - milvus
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
    deploy:
      resources:
        limits:
          cpus: '4'
          memory: 8G
        reservations:
          cpus: '2'
          memory: 4G

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

  milvus:
    image: milvusdb/milvus:v2.3.0
    ports:
      - "19530:19530"
    volumes:
      - milvus_data:/var/lib/milvus

volumes:
  redis_data:
  milvus_data:
```

---

## Kubernetes部署

### 1. 部署配置

```bash
# 应用配置
kubectl apply -f deploy/k8s/configmap.yaml
kubectl apply -f deploy/k8s/deployment.yaml
kubectl apply -f deploy/k8s/ingress.yaml
```

### 2. 查看状态

```bash
# 查看Pod
kubectl get pods -l app=rag-api

# 查看服务
kubectl get svc rag-api

# 查看Ingress
kubectl get ingress rag-api
```

### 3. 扩缩容

```bash
# 手动扩容
kubectl scale deployment rag-api --replicas=5

# 自动扩缩容 (HPA)
kubectl apply -f deploy/k8s/hpa.yaml
```

---

## 监控与日志

### 监控指标

```bash
# Prometheus查询示例
# QPS
rate(rag_requests_total[5m])

# P99延迟
histogram_quantile(0.99, rate(rag_latency_seconds_bucket[5m]))

# 错误率
rate(rag_errors_total[5m])
```

### 日志收集

```bash
# 查看实时日志
docker-compose logs -f api

# 查看最后100行
docker-compose logs --tail=100 api

# 导出日志
docker logs rag-api > api.log 2>&1
```

### Grafana面板

访问 http://localhost:3000，导入面板：
- 数据源: Prometheus
- 面板ID: 使用 `deploy/monitoring/grafana-dashboard.json`

---

## 常见问题

### Q1: 启动失败，提示"Module not found"

```bash
# 解决：检查Python路径
export PYTHONPATH="${PYTHONPATH}:./src"

# 或安装可编辑模式
pip install -e .
```

### Q2: 向量数据库连接失败

```bash
# 检查Milvus状态
docker-compose ps milvus

# 检查端口
telnet localhost 19530

# 重置数据
docker-compose down -v
docker-compose up -d
```

### Q3: GPU不可用

```bash
# 检查NVIDIA Docker
nvidia-docker run --rm nvidia/cuda:11.0-base nvidia-smi

# 安装NVIDIA Container Toolkit
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | tee /etc/apt/sources.list.d/nvidia-docker.list
apt-get update && apt-get install -y nvidia-container-toolkit
systemctl restart docker
```

### Q4: 内存不足

```bash
# 限制容器内存
docker run -m 4g --memory-swap 4g rag-api

# 或优化配置
# .env
BATCH_SIZE=16  # 减小批大小
MAX_WORKERS=2  # 减少工作线程
```

### Q5: API响应慢

```bash
# 检查瓶颈
# 1. 查看日志确认慢在哪个环节
# 2. 检查Redis缓存命中率
# 3. 优化向量索引（HNSW参数）
# 4. 启用查询缓存
```

---

## 升级指南

### 滚动升级

```bash
# 1. 构建新版本
docker build -t rag-enterprise-system:v1.1.0 .

# 2. 更新容器（零停机）
docker-compose up -d --no-deps --build api

# 3. 验证
sleep 10
curl http://localhost:8000/api/v1/health
```

### 数据库迁移

```bash
# 如果有schema变更
python scripts/migrate.py upgrade

# 回滚
python scripts/migrate.py downgrade
```

---

## 性能调优

### 系统级优化

```bash
# 文件描述符限制
ulimit -n 65535

# TCP优化
sysctl -w net.core.somaxconn=65535
sysctl -w net.ipv4.tcp_max_syn_backlog=65535
```

### 应用级优化

```python
# config/app.yaml
app:
  workers: 4              # 根据CPU核心数调整
  max_requests: 10000     # 重启阈值
  timeout: 300            # 超时时间

retrieval:
  batch_size: 32          # 批量大小
  top_k: 20               # 检索数量
  cache_ttl: 3600         # 缓存时间
```

---

## 安全建议

1. **API密钥**: 使用环境变量，不要硬编码
2. **HTTPS**: 生产环境必须启用
3. **防火墙**: 只开放必要端口
4. **审计日志**: 记录所有敏感操作
5. **RBAC**: 实施最小权限原则

---

## 支持

- Issue: https://github.com/JX-76/rag-enterprise-system/issues
- Email: your-email@example.com
