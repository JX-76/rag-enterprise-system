# 开发踩坑与问题解决记录

> **定位**：RAG Demo 开发全流程问题复盘，体现问题解决能力
> 
> **记录原则**：问题真实、原因清晰、方案可复现

---

## 踩坑 1：PDF 解析中文乱码问题

### 问题场景
上传 PDF 文件后，解析出的内容中文显示为乱码（如 `����`），无法正常向量化。

### 原因分析
1. **pypdf 编码支持不佳**：部分 PDF 使用非标准中文编码
2. **未指定编码格式**：默认解码方式为 ASCII，导致中文无法识别
3. **PDF 生成方式差异**：扫描件、某些 Word 导出的 PDF 编码不规范

### 解决方案
1. **改用 pdfplumber 作为补充解析工具**
   ```python
   # 原代码（pypdf）
   from pypdf import PdfReader
   reader = PdfReader(file_path)
   text = ""
   for page in reader.pages:
       text += page.extract_text()  # 中文乱码
   
   # 修复后（pdfplumber + 编码检测）
   import pdfplumber
   import chardet
   
   with pdfplumber.open(file_path) as pdf:
       text = ""
       for page in pdf.pages:
           page_text = page.extract_text()
           if page_text:
               # 强制 UTF-8 编码
               text += page_text.encode('utf-8', errors='ignore').decode('utf-8')
   ```

2. **添加编码回退机制**
   ```python
   def extract_pdf_text(file_path):
       """尝试多种方式解析 PDF"""
       # 方式1：pdfplumber（推荐）
       try:
           return extract_with_pdfplumber(file_path)
       except:
           pass
       
       # 方式2：pypdf（备用）
       try:
           return extract_with_pypdf(file_path)
       except:
           raise Exception("PDF 解析失败，请检查文件编码")
   ```

### 经验总结
- **不要依赖单一库**：PDF 解析没有银弹，需多方案兜底
- **显式指定编码**：`encode('utf-8', errors='ignore')` 避免默认编码问题
- **用户反馈友好**：解析失败返回明确提示，而非抛出技术栈

---

## 踩坑 2：向量检索精度过低问题

### 问题场景
用户查询 "机器学习是什么"，返回的文档片段与问题无关，答案偏离主题。

### 原因分析
1. **固定 token 分块割裂语义**
   ```
   原文："机器学习是人工智能的一个分支，它让计算机能够从数据中学习规律。"
   
   固定 10 token 分块：
   - 块1："机器学习是人工智能的"（语义不完整）
   - 块2："一个分支，它让计算机"（上下文丢失）
   ```

2. **单一向量检索覆盖不全**
   - Dense 向量检索擅长语义匹配，但可能漏掉关键词
   - 用户问 "决策树"，文档写 "Decision Tree"，向量相似度低

### 解决方案
1. **语义分块 + 固定长度兜底**
   ```python
   def semantic_chunk(text, chunk_size=512, overlap=64):
       """按段落/句子分块，保留语义完整性"""
       paragraphs = text.split('\n\n')
       chunks = []
       
       for para in paragraphs:
           if len(para) <= chunk_size:
               chunks.append(para)  # 短段落不拆分
           else:
               # 长段落按句子拆分
               sentences = re.split(r'(?<=[。！？])', para)
               current_chunk = ""
               for sent in sentences:
                   if len(current_chunk) + len(sent) <= chunk_size:
                       current_chunk += sent
                   else:
                       if current_chunk:
                           chunks.append(current_chunk)
                       current_chunk = sent
               if current_chunk:
                   chunks.append(current_chunk)
       
       return chunks
   ```

2. **混合检索（向量 + 关键词）**
   ```python
   class HybridRetriever:
       def search(self, query, top_k=5):
           # Dense 向量检索
           dense_results = self.vector_store.search(query_embedding, top_k=top_k*2)
           
           # BM25 关键词检索
           bm25_results = self.bm25_index.search(query, top_k=top_k*2)
           
           # RRF 融合排序
           fused_results = reciprocal_rank_fusion(dense_results, bm25_results, k=60)
           
           return fused_results[:top_k]
   ```

3. **分块重叠策略**
   ```python
   chunk_size = 512
   overlap = 64  # 12.5% 重叠
   
   for i in range(0, len(text), chunk_size - overlap):
       chunk = text[i:i + chunk_size]
   ```

### 经验总结
- **分块要考虑语义**：优先在段落、句子边界切分
- **单一检索策略不够**：Dense + Sparse 互补，RRF 融合效果提升明显
- **短文档特殊处理**：不超过 chunk_size 的不拆分，避免过度碎片化

---

## 踩坑 3：本地大模型显存溢出问题

### 问题场景
本地部署 Qwen-7B 模型，运行时报错 `CUDA out of memory`，程序崩溃。

### 原因分析
1. **模型未量化**：7B 模型 FP16 需要约 14GB 显存
2. **上下文窗口过长**：默认 4K tokens，显存占用随长度指数增长
3. **Batch 过大**：并发请求时显存叠加

### 解决方案
1. **4-bit 量化**
   ```python
   from transformers import AutoModelForCausalLM, BitsAndBytesConfig
   
   quantization_config = BitsAndBytesConfig(
       load_in_4bit=True,
       bnb_4bit_compute_dtype=torch.float16
   )
   
   model = AutoModelForCausalLM.from_pretrained(
       "Qwen/Qwen-7B-Chat",
       quantization_config=quantization_config,
       device_map="auto"
   )
   # 显存占用：14GB → 4GB
   ```

2. **限制上下文长度**
   ```python
   # config.py
   LLM_MAX_TOKENS = 1024  # 限制生成长度
   MAX_CONTEXT_LENGTH = 2048  # 限制输入上下文
   
   # 截断长文本
   if len(context) > MAX_CONTEXT_LENGTH:
       context = context[:MAX_CONTEXT_LENGTH]
   ```

3. **在线 API 兜底**
   ```python
   class LLMManager:
       def __init__(self):
           self.local_llm = None
           self.api_llm = DashScopeLLM()
           
       def generate(self, prompt):
           try:
               if self.local_llm:
                   return self.local_llm.generate(prompt)
           except CUDAOutOfMemory:
               logger.warning("本地模型显存不足，切换在线 API")
               return self.api_llm.generate(prompt)
   ```

4. **LM Studio 部署（更简单）**
   ```bash
   # 下载 LM Studio
   # 加载模型时选择 quantization: q4_k_m
   # 设置 Context Length: 2048
   # 启动本地服务器，API 地址: http://localhost:1234/v1
   ```

### 经验总结
- **量化是必须的**：4-bit 量化几乎无损，显存节省 70%+
- **上下文长度控制**：求职 Demo 不需要 4K/8K，1-2K 足够
- **本地+API 双模式**：本地跑不通时无缝切换，演示不翻车

---

## 踩坑 4：Milvus 容器连接失败问题

### 问题场景
Docker Compose 启动后，项目无法连接 Milvus，报错 `connection refused`。

### 原因分析
1. **端口映射错误**：docker-compose 中端口配置与代码不匹配
2. **容器启动顺序**：项目服务先于 Milvus 启动，连接时服务未就绪
3. **防火墙/网络问题**：宿主机防火墙拦截，或容器网络不通

### 解决方案
1. **统一端口配置**
   ```yaml
   # docker-compose.yml
   services:
     milvus:
       ports:
         - "19530:19530"
       environment:
         ETCD_ENDPOINTS: etcd:2379
         MINIO_ADDRESS: minio:9000
   ```
   ```python
   # config.py
   MILVUS_HOST = os.getenv("MILVUS_HOST", "localhost")
   MILVUS_PORT = int(os.getenv("MILVUS_PORT", 19530))
   ```

2. **健康检查 + 依赖等待**
   ```yaml
   services:
     milvus:
       healthcheck:
         test: ["CMD", "curl", "-f", "http://localhost:9091/healthz"]
         interval: 10s
         timeout: 5s
         retries: 5
     
     rag-demo:
       depends_on:
         milvus:
           condition: service_healthy
   ```

3. **连接重试机制**
   ```python
   from pymilvus import connections
   from tenacity import retry, stop_after_attempt, wait_fixed
   
   @retry(stop=stop_after_attempt(5), wait=wait_fixed(3))
   def connect_milvus():
       connections.connect(
           alias="default",
           host=settings.MILVUS_HOST,
           port=settings.MILVUS_PORT
       )
       print("Milvus 连接成功")
   ```

4. **网络诊断命令**
   ```bash
   # 检查容器状态
   docker-compose ps
   
   # 查看 Milvus 日志
   docker-compose logs milvus
   
   # 测试端口连通性
   docker exec -it rag-enterprise-system-milvus-1 curl localhost:9091/healthz
   
   # 从项目容器测试连接
   docker exec -it rag-enterprise-system-rag-demo-1 python -c "
   from pymilvus import connections
   connections.connect(host='milvus', port=19530)
   print('连接成功')
   "
   ```

### 经验总结
- **健康检查是必需的**：确保依赖服务就绪后再启动
- **连接重试避免偶发失败**：网络波动时自动恢复
- **日志排查优先**：`docker-compose logs` 是最快定位方式

---

## 踩坑 5：大模型幻觉问题

### 问题场景
用户问 "你们公司的年假政策是什么"，模型回答详细的年假规则，但知识库中根本没有相关内容。

### 原因分析
1. **Prompt 约束不足**：未明确要求模型基于检索文档回答
2. **无相关内容时未拒绝**：模型倾向于"编"而不是"说不知道"
3. **缺乏幻觉检测**：无法识别回答是否来自知识库

### 解决方案
1. **Prompt 工程优化**
   ```python
   RAG_PROMPT_TEMPLATE = """你是一位专业助手。请仅基于以下检索到的文档内容回答问题。
   如果文档中没有相关信息，请明确回答"未找到相关信息"，不要编造。
   
   === 检索到的文档 ===
   {retrieved_documents}
   
   === 用户问题 ===
   {question}
   
   === 回答要求 ===
   1. 仅使用文档中的信息
   2. 如果文档不相关，回答"未找到相关信息"
   3. 回答简洁准确
   
   请回答："""
   ```

2. **检索置信度判断**
   ```python
   def check_retrieval_quality(results, threshold=0.7):
       """检查检索结果质量"""
       if not results:
           return False, "无检索结果"
       
       top_score = results[0]["score"]
       if top_score < threshold:
           return False, f"检索置信度低（{top_score:.2f}）"
       
       return True, "检索质量合格"
   
   # 使用
   is_valid, msg = check_retrieval_quality(results)
   if not is_valid:
       return f"未找到相关信息（{msg}）"
   ```

3. **简单幻觉检测（相似度匹配）**
   ```python
   from sentence_transformers import SentenceTransformer
   
   def detect_hallucination(answer, source_documents):
       """检测回答是否与来源文档一致"""
       model = SentenceTransformer('BAAI/bge-small-zh-v1.5')
       
       # 编码回答和来源
       answer_emb = model.encode(answer)
       source_text = " ".join([doc["text"] for doc in source_documents])
       source_emb = model.encode(source_text)
       
       # 计算相似度
       similarity = cosine_similarity([answer_emb], [source_emb])[0][0]
       
       if similarity < 0.5:
           return True, f"疑似幻觉（相似度 {similarity:.2f}）"
       return False, "一致性良好"
   ```

### 经验总结
- **Prompt 约束是第一道防线**：明确"仅基于文档"、"不知道就说不知道"
- **置信度阈值可配置**：根据场景调整（严格场景 0.8，宽松场景 0.5）
- **幻觉检测是兜底**：相似度匹配简单但有效，后续可升级 NLI 模型

---

## 踩坑 6：API 接口跨域和参数校验问题

### 问题场景
前端调用接口时报错：
- `CORS error`：跨域被拦截
- `422 Unprocessable Entity`：参数格式错误
- `500 Internal Server Error`：异常未捕获

### 原因分析
1. **未配置 CORS**：FastAPI 默认不允许跨域
2. **参数类型不匹配**：前端传字符串，后端期望数字
3. **异常未全局捕获**：代码报错直接抛给用户

### 解决方案
1. **CORS 配置**
   ```python
   from fastapi.middleware.cors import CORSMiddleware
   
   app = FastAPI()
   
   app.add_middleware(
       CORSMiddleware,
       allow_origins=["*"],  # 生产环境应限制具体域名
       allow_credentials=True,
       allow_methods=["*"],
       allow_headers=["*"],
   )
   ```

2. **参数校验**
   ```python
   from pydantic import BaseModel, Field, validator
   from fastapi import UploadFile, File
   
   class QuestionRequest(BaseModel):
       question: str = Field(..., min_length=1, max_length=1000)
       session_id: str = Field(default="default")
       
       @validator('question')
       def question_not_empty(cls, v):
           if not v.strip():
               raise ValueError('问题不能为空')
           return v.strip()
   
   @app.post("/api/v1/chat/ask")
   async def ask(request: QuestionRequest):
       # 参数已自动校验
       ...
   
   # 文件上传校验
   @app.post("/api/v1/documents/upload")
   async def upload(file: UploadFile = File(...)):
       # 校验文件类型
       allowed_types = ['application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'text/plain']
       if file.content_type not in allowed_types:
           raise HTTPException(400, f"不支持的文件类型: {file.content_type}")
       
       # 校验文件大小
       max_size = 10 * 1024 * 1024  # 10MB
       content = await file.read()
       if len(content) > max_size:
           raise HTTPException(400, "文件大小超过 10MB 限制")
   ```

3. **全局异常捕获**
   ```python
   from fastapi import Request
   from fastapi.responses import JSONResponse
   
   @app.exception_handler(Exception)
   async def global_exception_handler(request: Request, exc: Exception):
       logger.error(f"未捕获异常: {exc}", exc_info=True)
       return JSONResponse(
           status_code=500,
           content={
               "error": "服务器内部错误",
               "message": str(exc) if settings.DEBUG else "请稍后重试"
           }
       )
   ```

### 经验总结
- **CORS 开发阶段开、生产阶段关**：开发时用 `*`，生产时指定域名
- **参数校验在前端之前**：后端必须校验，不信任前端
- **错误信息分级**：开发环境显示详情，生产环境隐藏敏感信息

---

## 踩坑 7：技术栈选型失误（Celery → 同步任务）

### 问题场景
初期选用 Celery + Redis 做异步文档处理，导致：
- 部署复杂：需额外启动 Redis、Celery Worker
- 调试困难：异步任务断点难打，日志分散
- 问题难定位：任务失败需查多个服务日志

### 原因分析
- **过度设计**：求职 Demo 不需要高并发异步处理
- **复杂度与收益不匹配**：节省的时间 < 增加的维护成本

### 解决方案
**简化方案：FastAPI 同步任务 + 后台线程**
```python
# 原方案：Celery
@celery.task
def process_document(doc_id):
    ...

# 简化方案：FastAPI BackgroundTasks
from fastapi import BackgroundTasks

@app.post("/api/v1/documents/upload")
async def upload(
    file: UploadFile,
    background_tasks: BackgroundTasks
):
    doc_id = save_file(file)
    # 后台处理，不阻塞响应
    background_tasks.add_task(process_document_sync, doc_id)
    return {"doc_id": doc_id, "status": "processing"}

def process_document_sync(doc_id):
    """同步处理，但放在后台任务中"""
    try:
        doc = load_document(doc_id)
        chunks = chunk_document(doc)
        vectors = embed_chunks(chunks)
        store_vectors(vectors)
        update_status(doc_id, "completed")
    except Exception as e:
        logger.error(f"处理失败: {e}")
        update_status(doc_id, "failed", error=str(e))
```

### 经验总结
- **选型要考虑维护成本**：Celery 是好工具，但小项目没必要
- **异步 ≠ 高性能**：对于 I/O 密集型，异步有优势；对于 CPU 密集型，多进程更合适
- **简单方案优先**：能用同步解决的，不用异步；能用单机的，不用分布式

---

## 总结：核心经验教训

### 1. 技术选型原则
- **简单优先**：SQLite 够用就不用 PostgreSQL
- **可维护性 > 先进性**：代码少、依赖少、调试容易
- **诚实面对局限性**：明确说明是 Demo，而非吹嘘生产级

### 2. 问题解决思路
- **日志优先**：先看报错信息，别瞎猜
- **隔离变量**：一次只改一个地方，定位问题根因
- **兜底方案**：主方案失败时有备选（本地模型 → 在线 API）

### 3. 求职展示技巧
- **讲清楚问题背景**：让面试官理解为什么难
- **突出解决过程**：不是一蹴而就，有尝试、有失败、有优化
- **诚实说明局限**：现在的方案有什么不足，后续怎么优化

---

*记录时间：2026-04-08*  
*项目版本：v2.0 求职实战版*
