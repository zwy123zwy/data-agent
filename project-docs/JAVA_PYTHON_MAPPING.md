# Python vs Java API 文件对应关系

## 📋 完整对应关系

| Python 文件 | Java 文件 | 说明 |
|------------|-----------|------|
| `agent_controller.py` | `AgentController.java` | Agent 管理 |
| `datasource_controller.py` | `DatasourceController.java` | 数据源管理 |
| `agent_datasource_controller.py` | `AgentDatasourceController.java` | Agent-数据源关联 |
| `agent_knowledge_controller.py` | `AgentKnowledgeController.java` | Agent 知识库管理 |
| `graph_controller.py` | `GraphController.java` | 工作流执行（非流式） |
| `streaming_graph_controller.py` | `GraphController.java` | 工作流执行（流式 SSE） |
| `schema_controller.py` | `DatasourceController.java` | Schema 查询（部分功能） |

---

## 🔍 详细说明

### 1. schema_controller.py

**对应**: `DatasourceController.java` 的部分功能

**原因**:
- Java 版本中，Schema 相关的接口在 `DatasourceController` 中
- 例如: `GET /api/datasource/{id}/tables` - 获取数据源的表列表
- Python 版本将 Schema 查询功能独立出来，提供更丰富的 API

**Java 版本的 Schema 功能**:
```java
// DatasourceController.java
@GetMapping("/{id}/tables")
public List<String> getDatasourceTables(@PathVariable Integer id)
```

**Python 版本扩展的 Schema 功能**:
```python
# schema_controller.py
GET /api/schema/datasources/{id}           # 获取完整 Schema（JSON）
GET /api/schema/datasources/{id}/ddl       # 获取 DDL（文本）
GET /api/schema/datasources/{id}/tables    # 获取所有表名
GET /api/schema/datasources/{id}/tables/{table}      # 获取单表结构
GET /api/schema/datasources/{id}/tables/{table}/ddl  # 获取单表 DDL
```

**为什么独立出来**:
- Python 版本提供了更详细的 Schema 查询能力
- 支持 LLM 友好的 DDL 文本格式
- 支持单表查询，更灵活

---

### 2. streaming_graph_controller.py

**对应**: `GraphController.java` 的流式接口

**原因**:
- Java 版本的 `GraphController` 只有一个流式接口
- Python 版本分为两个文件：
  - `graph_controller.py` - 非流式（阻塞式）
  - `streaming_graph_controller.py` - 流式（SSE）

**Java 版本**:
```java
// GraphController.java
@GetMapping(value = "/stream/search", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
public Flux<ServerSentEvent<GraphNodeResponse>> streamSearch(...)
```

**Python 版本**:
```python
# graph_controller.py
POST /api/query              # 非流式（Python 独有）

# streaming_graph_controller.py
POST /api/query/stream       # 流式 SSE（对应 Java 的 /stream/search）
```

**为什么分成两个文件**:
- Python 版本提供了两种查询方式（流式 + 非流式）
- Java 版本只提供流式接口
- 分离可以让代码更清晰

---

## 📊 对比总结

### Java 版本的设计
- `GraphController` - 只有流式接口
- `DatasourceController` - 包含数据源管理 + 部分 Schema 查询

### Python 版本的设计
- `graph_controller.py` - 非流式查询（新增）
- `streaming_graph_controller.py` - 流式查询（对应 Java）
- `schema_controller.py` - 独立的 Schema 查询（扩展 Java 功能）
- `datasource_controller.py` - 纯数据源管理

---

## 🎯 设计理念

### Python 版本的改进

1. **职责分离**
   - Schema 查询独立出来，不混在 Datasource 管理中
   - 流式和非流式查询分开，更清晰

2. **功能扩展**
   - Schema API 更丰富（DDL、单表查询等）
   - 提供非流式查询选项（简单场景更方便）

3. **命名一致性**
   - 所有文件都以 `_controller.py` 结尾
   - 与 Java 的 `Controller.java` 对应

---

## ✅ 结论

| Python 文件 | 对应 Java 文件 | 关系 |
|------------|---------------|------|
| `schema_controller.py` | `DatasourceController.java` | 扩展了 Schema 查询功能 |
| `streaming_graph_controller.py` | `GraphController.java` | 对应流式接口 |
| `graph_controller.py` | - | Python 独有（非流式查询） |

Python 版本在保持与 Java 版本对齐的同时，做了一些改进：
- 更细粒度的职责分离
- 更丰富的 Schema 查询 API
- 提供流式和非流式两种查询方式
