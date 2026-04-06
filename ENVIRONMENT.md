# 环境配置指南 - Environment Configuration

本文档详细说明各场景的环境配置要求。

---

## 📋 目录

1. [开发环境](#开发环境)
2. [测试环境](#测试环境)
3. [生产环境](#生产环境)
4. [场景特定配置](#场景特定配置)
5. [云服务配置](#云服务配置)
6. [GPU环境配置](#gpu环境配置)

---

## 开发环境

### 本地开发（Mac/Linux）

```bash
# 系统要求
macOS 12+ 或 Ubuntu 20.04+
Python 3.9+
8GB+ RAM

# 安装步骤
brew install python@3.11  # Mac
# 或
sudo apt-get install python3.11 python3.11-venv  # Ubuntu

# 创建虚拟环境
python3.11 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
pip install -r requirements-dev.txt  # 包含black, pytest等
```

### Windows开发

```powershell
# 使用WSL2（推荐）
# 或原生Windows

# 安装Python 3.11
# 从 https://python.org 下载安装

# 创建虚拟环境
python -m venv venv
venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt
```

### 开发环境配置 (.env.development)

```env
# 应用
APP_NAME=RAG-Enterprise-Dev
APP_ENV=development
DEBUG=true
LOG_LEVEL=DEBUG

# API（使用测试密钥或mock）
OPENAI_API_KEY=sk-test-key
# OPENAI_BASE_URL=https://api.openai.com/v1

# 向量数据库（本地Chroma）
VECTOR_STORE_TYPE=chroma
CHROMA_PERSIST_DIR=./data/chroma_dev

# 缓存（本地内存或Redis）
CACHE_TYPE=memory
# REDIS_URL=redis://localhost:6379/0

# Embedding（本地模型）
EMBEDDING_MODEL=BAAI/bge-small-zh
EMBEDDING_DEVICE=cpu

# 模型（使用小模型节省资源）
RERANK_MODEL_1=BAAI/bge-small-zh
RERANK_MODEL_2=BAAI/bge-reranker-base

# 限流（宽松）
RATE_LIMIT_ENABLED=false
RATE_LIMIT_RPM=10000

# 熔断（关闭或宽松）
CIRCUIT_BREAKER_ENABLED=false
```

---

## 测试环境

### CI/CD测试环境

```yaml
# .github/workflows/test.yml
name: Test

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      redis:
        image: redis:7-alpine
        ports:
          - 6379:6379
      
      milvus:
        image: milvusdb/milvus:v2.3.0
        ports:
          - 19530:19530
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-test.txt
      
      - name: Run tests
        run: pytest tests/ -v --cov=src
```

### 测试环境配置 (.env.staging)

```env
APP_NAME=RAG-Enterprise-Staging
APP_ENV=staging
DEBUG=false
LOG_LEVEL=INFO

# API（测试账户，有限额度）
OPENAI_API_KEY=sk-staging-key

# 向量数据库（测试实例）
VECTOR_STORE_TYPE=milvus
MILVUS_HOST=staging-milvus.internal
MILVUS_PORT=19530
MILVUS_USER=rag_staging
MILVUS_PASSWORD=your-secure-password

# 缓存（测试Redis）
CACHE_TYPE=redis
REDIS_URL=redis://staging-redis.internal:6379/0
REDIS_PASSWORD=your-redis-password

# Embedding（标准模型）
EMBEDDING_MODEL=BAAI/bge-m3
EMBEDDING_DEVICE=cuda

# 限流
RATE_LIMIT_ENABLED=true
RATE_LIMIT_RPM=1000

# 监控
PROMETHEUS_ENABLED=true
METRICS_PORT=9090
```

---

## 生产环境

### 高可用架构

```
┌─────────────────────────────────────────┐
│              负载均衡器 (Nginx/ALB)      │
└──────────────────┬──────────────────────┘
                   │
    ┌──────────────┼──────────────┐
    │              │              │
┌───▼───┐     ┌────▼───┐    ┌────▼───┐
│ API-1 │     │ API-2  │    │ API-3  │
└───┬───┘     └────┬───┘    └────┬───┘
    │              │              │
    └──────────────┼──────────────┘
                   │
    ┌──────────────┼──────────────┐
    │              │              │
┌───▼───┐     ┌────▼───┐    ┌────▼───┐
│Redis  │     │Milvus  │    │Prometheus
│集群   │     │集群    │    │+Grafana │
└───────┘     └────────┘    └─────────┘
```

### 生产环境配置 (.env.production)

```env
# 基础配置
APP_NAME=RAG-Enterprise-Prod
APP_ENV=production
DEBUG=false
LOG_LEVEL=WARNING
SECRET_KEY=your-256-bit-secret-key-here

# API密钥（主备）
OPENAI_API_KEY=sk-prod-primary-key
OPENAI_API_KEY_BACKUP=sk-prod-backup-key
ANTHROPIC_API_KEY=sk-anthropic-key

# 向量数据库（集群）
VECTOR_STORE_TYPE=milvus
MILVUS_HOST=milvus-proxy.internal
MILVUS_PORT=19530
MILVUS_USER=rag_prod
MILVUS_PASSWORD=your-strong-password
MILVUS_DB_NAME=rag_prod

# Redis（集群模式）
CACHE_TYPE=redis
REDIS_URL=redis://prod-redis.internal:6379/0
REDIS_PASSWORD=your-strong-redis-password
REDIS_SSL=true

# S3/OSS对象存储
STORAGE_TYPE=s3
S3_ENDPOINT=https://oss-cn-beijing.aliyuncs.com
S3_ACCESS_KEY=your-access-key
S3_SECRET_KEY=your-secret-key
S3_BUCKET=rag-documents-prod

# Embedding（高性能模型）
EMBEDDING_MODEL=BAAI/bge-m3
EMBEDDING_DEVICE=cuda
EMBEDDING_BATCH_SIZE=128

# 重排序模型
RERANK_MODEL_1=BAAI/bge-small-zh-v1.5
RERANK_MODEL_2=BAAI/bge-reranker-large

# 限流（严格）
RATE_LIMIT_ENABLED=true
RATE_LIMIT_RPM=1000
RATE_LIMIT_BURST=1500

# 熔断
CIRCUIT_BREAKER_ENABLED=true
CIRCUIT_FAILURE_THRESHOLD=5
CIRCUIT_RECOVERY_TIMEOUT=30

# 监控告警
PROMETHEUS_ENABLED=true
METRICS_PORT=9090
ALERT_ENABLED=true
ALERT_WEBHOOK=https://hooks.slack.com/your-webhook

# 审计
AUDIT_ENABLED=true
AUDIT_LOG_PATH=/var/log/rag/audit.log
AUDIT_RETENTION_DAYS=90

# 多租户
TENANCY_ENABLED=true
TENANT_ISOLATION=strict

# 安全
CORS_ORIGINS=https://yourdomain.com,https://app.yourdomain.com
SSL_ENABLED=true
TLS_MIN_VERSION=1.2
```

---

## 场景特定配置

### 场景1: 企业知识库

```env
# 数据量大，需要高性能检索
VECTOR_STORE_TYPE=milvus
MILVUS_COLLECTION=enterprise_kb
INDEX_TYPE=HNSW
HNSW_M=16
HNSW_EF_CONSTRUCTION=200
HNSW_EF_SEARCH=128

# 父子分块配置
CHUNK_PARENT_SIZE=1000
CHUNK_CHILD_SIZE=200
CHUNK_OVERLAP=50

# 权限控制
RBAC_ENABLED=true
DEFAULT_ROLE=employee
ADMIN_ROLES=admin,hr_admin

# 增量更新
INCREMENTAL_INDEXING=true
UPDATE_INTERVAL=3600
```

### 场景2: 法律文档审查

```env
# 高精度要求
RERANK_ENABLED=true
RERANK_TOP_K=10

# 审计严格
AUDIT_ENABLED=true
AUDIT_ALL_OPERATIONS=true
AUDIT_RETENTION_DAYS=2555  # 7年

# 数据加密
ENCRYPTION_AT_REST=true
ENCRYPTION_KEY_PATH=/etc/rag/encryption.key

# 合规
GDPR_COMPLIANT=true
DATA_RESIDENCY=CN
```

### 场景3: 医疗文献科研

```env
# 医学专用模型
EMBEDDING_MODEL=medical-bge-large
LLM_MODEL=medical-llm-v2

# 热更新
HOT_RELOAD_ENABLED=true
MODEL_WATCH_PATH=/models/

# 多租户（医院隔离）
TENANCY_ENABLED=true
TENANT_ISOLATION=strict

# 数据隔离
DATABASE_PER_TENANT=true
```

### 场景4: 电商智能客服

```env
# 高并发
WORKERS=8
MAX_CONNECTIONS=10000

# 缓存策略
CACHE_STRATEGY=aggressive
CACHE_TTL=300
CACHE_WARMUP=true

# AB测试
AB_TESTING_ENABLED=true
EXPERIMENTS=rerank_v2,prompt_v3

# 熔断（严格）
CIRCUIT_BREAKER_ENABLED=true
CIRCUIT_FAILURE_THRESHOLD=3
CIRCUIT_RECOVERY_TIMEOUT=10
```

### 场景5: 金融合规报告

```env
# 安全最高级别
SECURITY_LEVEL=high
MFA_REQUIRED=true
SESSION_TIMEOUT=900

# 审计
AUDIT_ENABLED=true
AUDIT_IMMUTABLE=true
AUDIT_BLOCKCHAIN=true

# 数据保留
DATA_RETENTION_DAYS=2555
ARCHIVE_ENABLED=true
ARCHIVE_S3_BUCKET=rag-archive-prod
```

### 场景6: 教育个性化答疑

```env
# 多租户（学校）
TENANCY_ENABLED=true
MAX_TENANTS=1000

# 成本控制
COST_OPTIMIZATION=true
LOCAL_EMBEDDING=true
CACHE_HIT_THRESHOLD=0.8

# 内容过滤
CONTENT_FILTER_ENABLED=true
INAPPROPRIATE_CONTENT_BLOCK=true
```

---

## 云服务配置

### AWS部署

```bash
# ECR镜像仓库
aws ecr create-repository --repository-name rag-enterprise

# ECS任务定义
aws ecs register-task-definition --cli-input-json file://deploy/aws/ecs-task.json

# RDS Redis
aws elasticache create-replication-group \
  --replication-group-id rag-redis \
  --engine redis \
  --cache-node-type cache.r6g.xlarge

# ALB
aws elbv2 create-load-balancer \
  --name rag-alb \
  --subnets subnet-xxxxx subnet-yyyyy \
  --security-groups sg-xxxxx
```

### 阿里云部署

```bash
# 容器镜像服务
aliyun cr CreateRepo --RepoName rag-enterprise

# ACK集群
aliyun cs POST /clusters \
  --body '{"name":"rag-cluster","region_id":"cn-beijing"}'

# Redis企业版
aliyun r-kvstore CreateInstance \
  --RegionId cn-beijing \
  --InstanceType Redis \
  --EngineVersion 6.0

# SLB
aliyun slb CreateLoadBalancer \
  --RegionId cn-beijing \
  --LoadBalancerName rag-slb
```

### 华为云部署

```bash
# SWR镜像仓库
hwcloud cr createRepo --name rag-enterprise

# CCE集群
hwcloud cce createCluster --name rag-cluster

# DCS Redis
hwcloud dcs createInstance --name rag-redis --capacity 8
```

---

## GPU环境配置

### NVIDIA GPU

```bash
# 安装驱动
# Ubuntu 22.04
sudo apt-get install nvidia-driver-535

# 安装CUDA
cd /tmp
wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/cuda-keyring_1.0-1_all.deb
sudo dpkg -i cuda-keyring_1.0-1_all.deb
sudo apt-get update
sudo apt-get install cuda-toolkit-12-2

# 验证
nvidia-smi
nvcc --version

# 安装PyTorch GPU版
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

### Docker GPU支持

```bash
# 安装NVIDIA Container Toolkit
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | \
  sudo tee /etc/apt/sources.list.d/nvidia-docker.list

sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit
sudo systemctl restart docker

# 测试
docker run --rm --gpus all nvidia/cuda:12.0-base nvidia-smi
```

### GPU配置 (.env.gpu)

```env
# GPU设置
CUDA_VISIBLE_DEVICES=0,1
EMBEDDING_DEVICE=cuda
EMBEDDING_BATCH_SIZE=256

# 显存优化
FP16_ENABLED=true
GRADIENT_CHECKPOINTING=true

# 多GPU
GPU_PARALLEL=true
GPU_COUNT=2
```

---

## 配置验证清单

### 部署前检查

```bash
# 1. 环境变量检查
python -c "from src.core.config import settings; print(settings.APP_ENV)"

# 2. 数据库连接检查
python scripts/check_db.py

# 3. API密钥检查
python scripts/check_api_keys.py

# 4. GPU检查
python -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}')"
```

### 部署后检查

```bash
# 1. 健康检查
curl http://localhost:8000/api/v1/health

# 2. 指标检查
curl http://localhost:9090/metrics

# 3. 日志检查
tail -f logs/app.log

# 4. 压力测试
python scripts/benchmark.py --qps 100 --duration 60
```

---

## 配置优先级

配置加载顺序（后加载覆盖先加载）：

1. `config/default.yaml` - 默认配置
2. `.env` - 环境变量
3. `.env.{ENV}` - 环境特定配置
4. 运行时参数 - 命令行参数

```python
# 优先级示例
# 命令行 > 环境特定 > 环境变量 > 默认
python src/main.py --workers 16  # 最高优先级
```

---

## 安全最佳实践

1. **密钥管理**: 使用AWS Secrets Manager / 阿里云KMS / HashiCorp Vault
2. **网络隔离**: 生产数据库不暴露公网
3. **SSL/TLS**: 强制HTTPS，TLS 1.2+
4. **定期轮换**: API密钥每90天轮换
5. **最小权限**: 数据库用户仅授予必要权限

```bash
# 密钥轮换脚本
python scripts/rotate_secrets.py
```
