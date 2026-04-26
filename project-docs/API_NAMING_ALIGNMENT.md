# API 文件命名对齐 Java 版本

## ✅ 重命名完成

### Python API 文件命名（对齐 Java Controller）

| Python 文件 | Java Controller | 说明 |
|------------|----------------|------|
| `agent_controller.py` | `AgentController.java` | Agent 管理 |
| `datasource_controller.py` | `DatasourceController.java` | 数据源管理 |
| `agent_datasource_controller.py` | `AgentDatasourceController.java` | Agent-数据源关联 |
| `agent_knowledge_controller.py` | `AgentKnowledgeController.java` | Agent 知识库管理 |
| `schema_controller.py` | - | Schema 查询（Python 独有） |
| `graph_controller.py` | `GraphController.java` | 工作流执行（非流式） |
| `streaming_graph_controller.py` | `GraphController.java` | 工作流执行（流式 SSE） |

### 命名规则

**Java 版本**:
- 文件名: `XxxController.java`
- 类名: `XxxController`

**Python 版本**:
- 文件名: `xxx_controller.py` (snake_case)
- 路由变量: `router`

### 对应关系

```
Java: AgentController.java
  ↓
Python: agent_controller.py
  ↓
导入: from app.api import agent_controller
  ↓
注册: app.include_router(agent_controller.router)
```

---

## 📋 完整 API 列表

### 1. AgentController
**文件**: `app/api/agent_controller.py`

- POST `/api/agents` - 创建 Agent
- GET `/api/agents` - 列出 Agent
- GET `/api/agents/{id}` - 获取 Agent 详情
- PUT `/api/agents/{id}` - 更新 Agent
- DELETE `/api/agents/{id}` - 删除 Agent
- POST `/api/agents/{id}/publish` - 发布 Agent
- POST `/api/agents/{id}/offline` - 下线 Agent

### 2. DatasourceController
**文件**: `app/api/datasource_controller.py`

- POST `/api/datasources` - 创建数据源
- GET `/api/datasources` - 列出数据源
- GET `/api/datasources/{id}` - 获取数据源详情
- PUT `/api/datasources/{id}` - 更新数据源
- DELETE `/api/datasources/{id}` - 删除数据源
- POST `/api/datasources/{id}/test` - 测试连接

### 3. AgentDatasourceController
**文件**: `app/api/agent_datasource_controller.py`

- POST `/api/agents/{agent_id}/datasources/{datasource_id}` - 绑定数据源
- DELETE `/api/agents/{agent_id}/datasources/{datasource_id}` - 解绑数据源
- GET `/api/agents/{agent_id}/datasources` - 列出数据源
- GET `/api/agents/{agent_id}/datasources/active` - 获取激活的数据源
- POST `/api/agents/{agent_id}/datasources/{datasource_id}/activate` - 激活数据源

### 4. AgentKnowledgeController
**文件**: `app/api/agent_knowledge_controller.py`

- POST `/api/agents/{agent_id}/knowledge` - 创建知识
- GET `/api/agents/{agent_id}/knowledge` - 列出知识
- GET `/api/agents/{agent_id}/knowledge/{id}` - 获取知识详情
- PUT `/api/agents/{agent_id}/knowledge/{id}` - 更新知识
- DELETE `/api/agents/{agent_id}/knowledge/{id}` - 删除知识
- POST `/api/agents/{agent_id}/knowledge/search` - 向量检索知识

### 5. SchemaController
**文件**: `app/api/schema_controller.py`

- GET `/api/schema/datasources/{id}` - 获取数据源 Schema（JSON）
- GET `/api/schema/datasources/{id}/ddl` - 获取数据源 DDL（文本）
- GET `/api/schema/datasources/{id}/tables` - 获取所有表名
- GET `/api/schema/datasources/{id}/tables/{table}` - 获取单表结构
- GET `/api/schema/datasources/{id}/tables/{table}/ddl` - 获取单表 DDL

### 6. GraphController
**文件**: `app/api/graph_controller.py`

- POST `/api/query` - 执行查询（非流式，阻塞式）

### 7. StreamingGraphController
**文件**: `app/api/streaming_graph_controller.py`

- POST `/api/query/stream` - 执行查询（流式 SSE）

---

## 🔄 Java vs Python 对比

### Java 版本的 Controller

```
AgentController.java
DatasourceController.java
AgentDatasourceController.java
AgentKnowledgeController.java
BusinessKnowledgeController.java
GraphController.java
ModelConfigController.java
PromptConfigController.java
SemanticModelController.java
ChatController.java
FileUploadController.java
SessionEventController.java
...
```

### Python 版本已实现

```
✅ agent_controller.py
✅ datasource_controller.py
✅ agent_datasource_controller.py
✅ agent_knowledge_controller.py
✅ schema_controller.py (Python 独有)
✅ graph_controller.py
✅ streaming_graph_controller.py
```

### Python 版本待实现（Phase 3+）

```
⏳ business_knowledge_controller.py
⏳ model_config_controller.py
⏳ prompt_config_controller.py
⏳ semantic_model_controller.py
⏳ chat_controller.py
⏳ file_upload_controller.py
⏳ session_event_controller.py
```

---

## 📝 更新内容

### 文件重命名

```bash
agents.py → agent_controller.py
datasources.py → datasource_controller.py
agent_datasources.py → agent_datasource_controller.py
knowledge.py → agent_knowledge_controller.py
schema.py → schema_controller.py
query.py → graph_controller.py
streaming_query.py → streaming_graph_controller.py
```

### main.py 更新

```python
# 导入
from .api import (
    agent_controller,
    datasource_controller,
    agent_datasource_controller,
    agent_knowledge_controller,
    schema_controller,
    graph_controller,
    streaming_graph_controller
)

# 注册路由
app.include_router(agent_controller.router)
app.include_router(datasource_controller.router)
app.include_router(agent_datasource_controller.router)
app.include_router(agent_knowledge_controller.router)
app.include_router(schema_controller.router)
app.include_router(graph_controller.router)
app.include_router(streaming_graph_controller.router)
```

---

## ✅ 总结

所有 API 文件已重命名为与 Java 版本一致的命名风格：

- **Java**: `XxxController.java`
- **Python**: `xxx_controller.py`

这样可以更容易地在两个版本之间对照和理解代码结构。
