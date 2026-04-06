# 生产环境RAG的熔断与限流：从玩具到企业级

> 从实验室Demo到线上服务，差的不只是代码，而是对故障的敬畏。

## 引言

做RAG系统的人，十个里有九个卡在检索精度，只有一个想过：**如果向量数据库挂了怎么办？**

这就是玩具和产品的区别。

这篇文章分享我们在企业级RAG系统中实现熔断和限流的完整方案，包含：
- 为什么需要熔断限流（真实故障案例）
- 状态机熔断器的设计与实现
- Token Bucket限流的多级策略
- 从故障到恢复的完整链路

---

## 一、一个真实的故障

### 场景

2024年Q1，我们内部知识库系统上线。架构很简单：

```
用户查询 → FastAPI → 向量检索(Milvus) → LLM生成 → 返回
```

某天下午，Milvus集群因为磁盘满了开始超时。

### 故障链路

```
14:32 Milvus磁盘100% → 查询超时(30s)
14:33 用户开始重试 → 请求堆积
14:34 FastAPI连接池耗尽 → 新请求无法接入
14:35 全系统雪崩 → 502错误
14:40 人工介入重启 → 恢复
```

**直接损失**: 25分钟服务不可用，200+用户投诉。

### 根因分析

根本原因不是Milvus挂了，而是**级联故障**：

1. **无熔断**: 下游超时，上游继续等，资源被占满
2. **无限流**: 重试风暴把系统压垮
3. **无降级**: 没有Plan B，只能硬扛

---

## 二、熔断器设计

### 核心思想

Netflix Hystrix的经典设计：
- **CLOSED**: 正常，请求通过
- **OPEN**: 熔断，快速失败
- **HALF_OPEN**: 试探，验证恢复

### 状态机实现

```python
class CircuitState(Enum):
    CLOSED = "closed"      # 正常
    OPEN = "open"          # 熔断
    HALF_OPEN = "half_open"  # 半开

class CircuitBreaker:
    def __init__(self, failure_threshold=5, recovery_timeout=30):
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
    
    async def call(self, func, *args, **kwargs):
        if self.state == CircuitState.OPEN:
            # 检查是否可以进入半开状态
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
            else:
                raise CircuitBreakerOpen("熔断中")
        
        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except Exception:
            self._on_failure()
            raise
```

### 关键决策点

| 参数 | 值 | 原因 |
|------|----|------|
| failure_threshold | 5次 | 避免偶发抖动误熔断 |
| recovery_timeout | 30秒 | Milvus重启平均时间 |
| half_open_max_calls | 3次 | 足够验证，不会压垮 |

### 代码实战

```python
# 为向量数据库添加熔断保护
vector_db_breaker = CircuitBreaker(
    name="milvus",
    failure_threshold=3,
    recovery_timeout=30.0
)

@app.post("/query")
async def query(request: QueryRequest):
    try:
        # 受熔断保护的调用
        results = await vector_db_breaker.call(
            milvus_client.search,
            request.query,
            top_k=10
        )
        return {"results": results}
    except CircuitBreakerOpen:
        # 降级策略：返回缓存或使用备用检索
        return await fallback_search(request.query)
```

### 效果验证

熔断开启后，系统表现：

```
熔断前:
- Milvus超时(30s) → 用户等待 → 重试 → 雪崩

熔断后:
- Milvus超时(30s) → 第3次失败 → 熔断开启
- 后续请求: 立即返回503 (0ms)
- 30秒后: 进入半开状态，试探3个请求
- 恢复后: 关闭熔断，正常服务
```

**MTTR (平均恢复时间)**: 25分钟 → 30秒

---

## 三、限流器设计

### 多级限流策略

企业级系统需要多层保护：

```
┌─────────────────────────────────────────┐
│  全局总限流: 10,000 QPS (系统容量)        │
├─────────────────────────────────────────┤
│  API级别:                                 │
│   - /query: 100 QPS (计算密集)           │
│   - /health: 10,000 QPS (轻量)           │
│   - /ingest: 10 QPS (写入严格)           │
├─────────────────────────────────────────┤
│  用户级别:                                │
│   - 普通用户: 100 RPM                    │
│   - VIP用户: 10,000 RPM                  │
├─────────────────────────────────────────┤
│  IP级别: 防刷保护                          │
└─────────────────────────────────────────┘
```

### Token Bucket算法

```python
class TokenBucket:
    def __init__(self, rate: float, capacity: int):
        self.rate = rate          # 每秒产生token数
        self.capacity = capacity  # 桶容量
        self.tokens = capacity
        self.last_update = time.time()
    
    async def acquire(self, tokens: int = 1) -> bool:
        now = time.time()
        elapsed = now - self.last_update
        
        # 补充token
        self.tokens = min(
            self.capacity,
            self.tokens + elapsed * self.rate
        )
        self.last_update = now
        
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False
```

**为什么选Token Bucket而不是Fixed Window？**

- Fixed Window: 窗口边界突刺（59秒和01秒各来一波）
- Token Bucket: 平滑限流，支持突发

### 实战配置

```python
# 不同API不同限流策略
RATE_LIMIT_CONFIG = {
    "/api/v1/query": {
        "rate": 100,      # 100 QPS
        "burst": 150,     # 突发150
        "reason": "向量检索计算密集，保护Milvus"
    },
    "/api/v1/health": {
        "rate": 10000,    # 几乎不限
        "burst": 20000,
        "reason": "健康检查必须快速响应"
    },
    "/api/v1/ingest": {
        "rate": 10,       # 严格限流
        "burst": 20,
        "reason": "写入操作，避免索引压力过大"
    }
}
```

---

## 四、熔断+限流的协同

### 完整链路

```
用户请求
   ↓
[限流检查] ──超限──► 429 Too Many Requests
   ↓ 通过
[熔断检查] ──熔断──► 503 + 降级响应
   ↓ 正常
[业务逻辑] ──异常──► 记录失败，可能触发熔断
   ↓ 成功
[返回结果]
```

### 监控指标

```python
# Prometheus指标
CIRCUIT_BREAKER_STATE = Gauge(
    'rag_circuit_breaker_state',
    'Circuit breaker state (0=closed, 1=open, 2=half_open)',
    ['name']
)

RATE_LIMIT_HITS = Counter(
    'rag_rate_limit_hits_total',
    'Rate limit hits',
    ['path', 'type']
)

# 告警规则
- 熔断开启超过5分钟 → P1告警
- 限流命中率超过10% → P2告警
- 降级响应超过1% → P2告警
```

---

## 五、从故障中学到的

### 1. 不要信任任何下游

> "任何可能出错的事都会出错" —— 墨菲定律

- 数据库会超时
- LLM会限流
- 网络会抖动

熔断器是给下游的**保险丝**。

### 2. 优雅降级比完美更重要

```python
async def fallback_search(query: str):
    """降级策略"""
    # 1. 查缓存
    if cached := await cache.get(query):
        return cached
    
    # 2. 用BM25替代向量检索
    return await bm25_search(query)
    
    # 3. 返回提示
    return {"error": "搜索服务繁忙，请稍后重试"}
```

### 3. 监控比代码更重要

没有监控的熔断器是瞎子：
- 不知道熔断触发了
- 不知道恢复没有
- 不知道什么时候该调参数

---

## 六、代码与资源

**完整代码**: [GitHub - rag-enterprise-system](https://github.com/JX-76/rag-enterprise-system)

核心文件:
- `src/api/middleware/circuit_breaker.py`
- `src/api/middleware/rate_limit.py`

**测试**: 
```bash
python scripts/test_circuit_breaker.py
python scripts/test_rate_limit.py
```

---

## 结语

熔断和限流是**防御性编程**的核心。

它们不会让你的RAG检索更准，但会让你的系统在故障时：**不崩溃、可预期、能恢复**。

这才是从Demo到产品的差距。

---

*作者: JX-76 | 项目: [rag-enterprise-system](https://github.com/JX-76/rag-enterprise-system) | 欢迎Star和Issue*