# 流式输出实现文档

## ✅ 已实现

### 1. 流式查询 API
**文件**: `app/api/streaming_query.py`

**接口**: `POST /api/query/stream`

使用 **SSE (Server-Sent Events)** 实现实时流式输出。

### 2. 流式 LLM 服务
**文件**: `app/core/streaming_llm.py`

提供两种模式：
- `chat()` - 阻塞式调用（等待完整响应）
- `chat_stream()` - 流式调用（逐 token 返回）

---

## 📡 SSE 事件类型

流式查询会推送以下事件：

| 事件类型 | 说明 | 数据格式 |
|---------|------|---------|
| `start` | 开始处理 | `{"message": "开始处理查询"}` |
| `intent` | 意图识别结果 | `{"intent": "data_analysis"}` |
| `knowledge` | 知识召回结果 | `{"knowledge": "相关知识..."}` |
| `rewrite` | 查询改写结果 | `{"rewritten_query": "改写后的查询"}` |
| `schema` | Schema 召回完成 | `{"message": "Schema 召回完成"}` |
| `sql` | SQL 生成结果 | `{"sql": "SELECT ..."}` |
| `sql_result` | SQL 执行结果 | `{"result": [...], "count": 10}` |
| `sql_error` | SQL 执行错误 | `{"error": "错误信息"}` |
| `report` | 最终报告 | `{"report": "分析报告..."}` |
| `done` | 处理完成 | `{"message": "查询完成"}` |
| `error` | 错误信息 | `{"error": "错误描述"}` |

---

## 🚀 使用示例

### 1. curl 测试

```bash
curl -N -X POST "http://localhost:8100/api/query/stream" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": 1,
    "query": "查询所有用户"
  }'
```

**输出示例**:
```
event: start
data: {"message": "开始处理查询"}

event: intent
data: {"intent": "data_analysis"}

event: knowledge
data: {"knowledge": "相关知识:\n1. 用户表\n   类型: business_term\n   内容: users 表存储用户信息"}

event: rewrite
data: {"rewritten_query": "查询 users 表的所有记录"}

event: schema
data: {"message": "Schema 召回完成"}

event: sql
data: {"sql": "SELECT * FROM users"}

event: sql_result
data: {"result": [{"id": 1, "name": "张三"}], "count": 1}

event: report
data: {"report": "查询到 1 条用户记录"}

event: done
data: {"message": "查询完成"}
```

### 2. JavaScript 客户端

```javascript
const eventSource = new EventSource('http://localhost:8100/api/query/stream', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    agent_id: 1,
    query: '查询所有用户'
  })
});

// 监听不同事件
eventSource.addEventListener('start', (e) => {
  console.log('开始:', JSON.parse(e.data));
});

eventSource.addEventListener('intent', (e) => {
  console.log('意图:', JSON.parse(e.data));
});

eventSource.addEventListener('sql', (e) => {
  console.log('SQL:', JSON.parse(e.data));
});

eventSource.addEventListener('sql_result', (e) => {
  console.log('结果:', JSON.parse(e.data));
});

eventSource.addEventListener('report', (e) => {
  console.log('报告:', JSON.parse(e.data));
});

eventSource.addEventListener('done', (e) => {
  console.log('完成:', JSON.parse(e.data));
  eventSource.close();
});

eventSource.addEventListener('error', (e) => {
  console.error('错误:', JSON.parse(e.data));
  eventSource.close();
});
```

### 3. Python 客户端

```python
import httpx
import json

async def stream_query():
    async with httpx.AsyncClient() as client:
        async with client.stream(
            'POST',
            'http://localhost:8100/api/query/stream',
            json={'agent_id': 1, 'query': '查询所有用户'},
            timeout=60.0
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith('event:'):
                    event_type = line.split(':', 1)[1].strip()
                elif line.startswith('data:'):
                    data = json.loads(line.split(':', 1)[1].strip())
                    print(f"{event_type}: {data}")

# 运行
import asyncio
asyncio.run(stream_query())
```

---

## 🔄 工作流执行流程

```
用户请求
  ↓
event: start
  ↓
意图识别 → event: intent
  ↓
知识召回 → event: knowledge
  ↓
查询改写 → event: rewrite
  ↓
Schema 召回 → event: schema
  ↓
SQL 生成 → event: sql
  ↓
SQL 执行 → event: sql_result (或 sql_error)
  ↓
报告生成 → event: report
  ↓
event: done
```

---

## 🎯 对比非流式接口

| 特性 | 非流式 (`/api/query`) | 流式 (`/api/query/stream`) |
|------|---------------------|--------------------------|
| 响应方式 | 一次性返回完整结果 | 实时推送执行进度 |
| 用户体验 | 需要等待全部完成 | 实时看到进度 |
| 超时风险 | 长查询可能超时 | 持续连接，不易超时 |
| 调试友好度 | 只能看到最终结果 | 可以看到每个节点的输出 |
| 适用场景 | 简单快速查询 | 复杂长时间查询 |

---

## 📝 注意事项

### 1. Nginx 配置
如果使用 Nginx 反向代理，需要禁用缓冲：

```nginx
location /api/query/stream {
    proxy_pass http://backend;
    proxy_buffering off;
    proxy_cache off;
    proxy_set_header Connection '';
    proxy_http_version 1.1;
    chunked_transfer_encoding off;
}
```

### 2. 超时设置
流式查询可能需要较长时间，建议设置合理的超时：

```python
# FastAPI 启动时
uvicorn.run(
    "app.main:app",
    timeout_keep_alive=300  # 5 分钟
)
```

### 3. 错误处理
流式输出中如果发生错误，会发送 `error` 事件，客户端应该监听并处理。

---

## 🔮 未来增强

### 1. LLM 流式输出
可以将 LLM 的流式响应也推送给客户端：

```python
# 在 sql_generate_node 中
async for chunk in streaming_llm_service.chat_stream(system_prompt, user_prompt):
    yield f"event: llm_chunk\ndata: {json.dumps({'chunk': chunk})}\n\n"
```

### 2. 进度百分比
添加进度跟踪：

```python
yield f"event: progress\ndata: {json.dumps({'percent': 60, 'step': 'SQL执行中'})}\n\n"
```

### 3. 中断支持
允许客户端中断长时间运行的查询。

---

## ✅ 总结

现在系统支持两种查询方式：

1. **非流式** (`POST /api/query`) - 简单快速查询
2. **流式** (`POST /api/query/stream`) - 复杂查询，实时反馈

流式接口使用 SSE 推送 11 种事件类型，覆盖工作流的每个节点，提供完整的执行可见性。
