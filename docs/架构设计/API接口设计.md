# API 设计文档

## API 概览

Phase 1 提供 3 组 API：
1. **Agent 管理** - Agent CRUD 操作
2. **Datasource 管理** - 数据源 CRUD 和测试
3. **查询执行** - 核心 Text-to-SQL 功能

---

## 基础信息

- **Base URL**: `http://localhost:8200`
- **API 前缀**: `/api`
- **Content-Type**: `application/json`
- **文档地址**: `http://localhost:8200/docs` (Swagger UI)

---

## 1. Agent 管理 API

### 1.1 创建 Agent

**接口**: `POST /api/agents`

**请求体**:
```json
{
  "name": "销售分析助手",
  "description": "分析销售数据，生成销售报告"
}
```

**响应**: `201 Created`
```json
{
  "id": 1,
  "name": "销售分析助手",
  "description": "分析销售数据，生成销售报告",
  "status": "draft",
  "created_at": "2024-01-01T10:00:00",
  "updated_at": "2024-01-01T10:00:00"
}
```

**错误响应**:
```json
{
  "detail": "Agent name already exists"
}
```

---

### 1.2 列出所有 Agent

**接口**: `GET /api/agents`

**查询参数**:
- `status` (可选): 过滤状态 (`draft`, `published`, `offline`)
- `skip` (可选): 分页偏移，默认 0
- `limit` (可选): 每页数量，默认 100

**示例**: `GET /api/agents?status=published&skip=0&limit=10`

**响应**: `200 OK`
```json
[
  {
    "id": 1,
    "name": "销售分析助手",
    "description": "分析销售数据，生成销售报告",
    "status": "published",
    "created_at": "2024-01-01T10:00:00",
    "updated_at": "2024-01-01T10:00:00"
  },
  {
    "id": 2,
    "name": "用户行为分析",
    "description": "分析用户行为数据",
    "status": "draft",
    "created_at": "2024-01-02T10:00:00",
    "updated_at": "2024-01-02T10:00:00"
  }
]
```

---

### 1.3 获取 Agent 详情

**接口**: `GET /api/agents/{agent_id}`

**路径参数**:
- `agent_id`: Agent ID

**响应**: `200 OK`
```json
{
  "id": 1,
  "name": "销售分析助手",
  "description": "分析销售数据，生成销售报告",
  "status": "published",
  "created_at": "2024-01-01T10:00:00",
  "updated_at": "2024-01-01T10:00:00"
}
```

**错误响应**: `404 Not Found`
```json
{
  "detail": "Agent not found"
}
```

---

### 1.4 更新 Agent

**接口**: `PUT /api/agents/{agent_id}`

**路径参数**:
- `agent_id`: Agent ID

**请求体**:
```json
{
  "name": "销售分析助手 V2",
  "description": "更新后的描述",
  "status": "published"
}
```

**响应**: `200 OK`
```json
{
  "id": 1,
  "name": "销售分析助手 V2",
  "description": "更新后的描述",
  "status": "published",
  "created_at": "2024-01-01T10:00:00",
  "updated_at": "2024-01-01T11:00:00"
}
```

---

### 1.5 删除 Agent

**接口**: `DELETE /api/agents/{agent_id}`

**路径参数**:
- `agent_id`: Agent ID

**响应**: `204 No Content`

**错误响应**: `404 Not Found`

---

## 2. Datasource 管理 API

### 2.1 创建数据源

**接口**: `POST /api/datasources`

**请求体 (MySQL)**:
```json
{
  "name": "生产数据库",
  "type": "mysql",
  "host": "localhost",
  "port": 3306,
  "database": "sales_db",
  "username": "root",
  "password": "password"
}
```

**请求体 (SQLite)**:
```json
{
  "name": "本地测试库",
  "type": "sqlite",
  "database": "test.db",
  "connection_url": "sqlite:///./test.db"
}
```

**响应**: `201 Created`
```json
{
  "id": 1,
  "name": "生产数据库",
  "type": "mysql",
  "database": "sales_db",
  "test_status": "untested",
  "created_at": "2024-01-01T10:00:00"
}
```

---

### 2.2 列出所有数据源

**接口**: `GET /api/datasources`

**查询参数**:
- `type` (可选): 过滤类型 (`mysql`, `postgresql`, `sqlite`)
- `skip` (可选): 分页偏移，默认 0
- `limit` (可选): 每页数量，默认 100

**响应**: `200 OK`
```json
[
  {
    "id": 1,
    "name": "生产数据库",
    "type": "mysql",
    "database": "sales_db",
    "test_status": "success",
    "created_at": "2024-01-01T10:00:00"
  },
  {
    "id": 2,
    "name": "本地测试库",
    "type": "sqlite",
    "database": "test.db",
    "test_status": "success",
    "created_at": "2024-01-02T10:00:00"
  }
]
```

---

### 2.3 获取数据源详情

**接口**: `GET /api/datasources/{datasource_id}`

**响应**: `200 OK`
```json
{
  "id": 1,
  "name": "生产数据库",
  "type": "mysql",
  "host": "localhost",
  "port": 3306,
  "database": "sales_db",
  "username": "root",
  "test_status": "success",
  "created_at": "2024-01-01T10:00:00",
  "updated_at": "2024-01-01T10:00:00"
}
```

**注意**: 密码字段不会返回

---

### 2.4 测试数据源连接

**接口**: `POST /api/datasources/{datasource_id}/test`

**响应**: `200 OK`
```json
{
  "success": true,
  "message": "Connection successful",
  "test_status": "success"
}
```

**错误响应**: `200 OK` (测试失败不返回 4xx)
```json
{
  "success": false,
  "message": "Connection failed: Access denied for user 'root'@'localhost'",
  "test_status": "failed"
}
```

---

### 2.5 删除数据源

**接口**: `DELETE /api/datasources/{datasource_id}`

**响应**: `204 No Content`

---

## 3. Agent-Datasource 关联 API

### 3.1 绑定数据源到 Agent

**接口**: `POST /api/agents/{agent_id}/datasources/{datasource_id}`

**路径参数**:
- `agent_id`: Agent ID
- `datasource_id`: Datasource ID

**请求体** (可选):
```json
{
  "is_active": true
}
```

**响应**: `201 Created`
```json
{
  "id": 1,
  "agent_id": 1,
  "datasource_id": 1,
  "is_active": true,
  "created_at": "2024-01-01T10:00:00"
}
```

**错误响应**:
```json
{
  "detail": "Agent or Datasource not found"
}
```

---

### 3.2 列出 Agent 的数据源

**接口**: `GET /api/agents/{agent_id}/datasources`

**响应**: `200 OK`
```json
[
  {
    "id": 1,
    "agent_id": 1,
    "datasource_id": 1,
    "is_active": true,
    "created_at": "2024-01-01T10:00:00",
    "datasource": {
      "id": 1,
      "name": "生产数据库",
      "type": "mysql",
      "database": "sales_db",
      "test_status": "success"
    }
  }
]
```

---

### 3.3 解绑数据源

**接口**: `DELETE /api/agents/{agent_id}/datasources/{datasource_id}`

**响应**: `204 No Content`

---

## 4. 查询执行 API (核心)

### 4.1 执行查询

**接口**: `POST /api/query`

**请求体**:
```json
{
  "agent_id": 1,
  "query": "查询销售额最高的前10个产品"
}
```

**响应**: `200 OK`
```json
{
  "intent": "data_analysis",
  "sql": "SELECT product_name, SUM(amount) as total_sales FROM sales GROUP BY product_name ORDER BY total_sales DESC LIMIT 10",
  "result": [
    {
      "product_name": "产品A",
      "total_sales": 10000
    },
    {
      "product_name": "产品B",
      "total_sales": 8000
    }
  ],
  "report": "根据查询结果，销售额最高的产品是产品A，总销售额为10000元。其次是产品B，销售额为8000元。前10个产品的销售额总计为50000元。",
  "error": null
}
```

**意图为闲聊的响应**:
```json
{
  "intent": "chitchat",
  "sql": null,
  "result": null,
  "report": "您好！我是数据分析助手，专门帮助您分析数据。请问有什么数据分析需求吗？",
  "error": null
}
```

**错误响应**: `400 Bad Request`
```json
{
  "intent": "data_analysis",
  "sql": "SELECT * FROM non_existent_table",
  "result": null,
  "report": null,
  "error": "SQL execution failed: Table 'sales_db.non_existent_table' doesn't exist"
}
```

---

## 错误响应格式

所有错误响应遵循统一格式：

```json
{
  "detail": "错误描述信息"
}
```

### HTTP 状态码

- `200 OK` - 请求成功
- `201 Created` - 资源创建成功
- `204 No Content` - 删除成功
- `400 Bad Request` - 请求参数错误
- `404 Not Found` - 资源不存在
- `422 Unprocessable Entity` - 数据验证失败
- `500 Internal Server Error` - 服务器内部错误

---

## 数据验证规则

### Agent
- `name`: 必填，最大长度 100
- `description`: 可选，文本类型
- `status`: 必须是 `draft`, `published`, `offline` 之一

### Datasource
- `name`: 必填，最大长度 100
- `type`: 必填，必须是 `mysql`, `postgresql`, `sqlite` 之一
- `database`: 必填，最大长度 100
- `host`: MySQL/PostgreSQL 必填
- `port`: MySQL/PostgreSQL 必填，整数
- `username`: MySQL/PostgreSQL 必填
- `password`: MySQL/PostgreSQL 必填
- `connection_url`: SQLite 必填

### Query
- `agent_id`: 必填，整数
- `query`: 必填，最小长度 1

---

## 请求示例 (cURL)

### 创建 Agent
```bash
curl -X POST "http://localhost:8200/api/agents" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "销售分析助手",
    "description": "分析销售数据"
  }'
```

### 创建数据源
```bash
curl -X POST "http://localhost:8200/api/datasources" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "生产数据库",
    "type": "mysql",
    "host": "localhost",
    "port": 3306,
    "database": "sales_db",
    "username": "root",
    "password": "password"
  }'
```

### 绑定数据源
```bash
curl -X POST "http://localhost:8200/api/agents/1/datasources/1" \
  -H "Content-Type: application/json"
```

### 执行查询
```bash
curl -X POST "http://localhost:8200/api/query" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": 1,
    "query": "查询销售额最高的前10个产品"
  }'
```

---

## 与 Java 版本对齐

| Java 接口 | Python 接口 | Phase | 说明 |
|-----------|-------------|-------|------|
| POST /api/agent | POST /api/agents | 1 | ✅ 对齐 |
| GET /api/agent/list | GET /api/agents | 1 | ✅ 对齐 |
| GET /api/agent/{id} | GET /api/agents/{id} | 1 | ✅ 对齐 |
| POST /api/datasource | POST /api/datasources | 1 | ✅ 对齐 |
| GET /api/datasource | GET /api/datasources | 1 | ✅ 对齐 |
| POST /api/datasource/{id}/test | POST /api/datasources/{id}/test | 1 | ✅ 对齐 |
| POST /api/query | POST /api/query | 1 | ✅ 对齐 (简化版) |
| GET /api/stream/search | - | 2+ | 待实现 (流式) |

---

## 后续 Phase 扩展

### Phase 2
- `GET /api/stream/search` - SSE 流式查询
- `POST /api/business-knowledge` - 业务知识管理
- `POST /api/semantic-model` - 语义模型管理

### Phase 3
- `POST /api/agent/{id}/sessions` - 创建会话
- `GET /api/sessions/{id}/messages` - 获取消息历史

### Phase 4
- `POST /api/prompt-config` - Prompt 配置
- `POST /api/model-config` - 模型配置

### Phase 5
- `POST /api/agent/{id}/publish` - 发布 Agent
- `POST /api/agent/{id}/api-key/generate` - 生成 API Key
