# Python 后端 vs Java 后端 API 对齐分析

> Java 来源: `DataAgent/data-agent-management/.../controller/` (12 个控制器, ~80 个端点)
> Python 来源: `python-agent-v2/app/api/` (12 个控制器, ~50 个端点)
> 分析日期: 2026-05-03

## 总览

| | Java | Python | 对齐率 |
|---|------|--------|--------|
| 控制器数量 | 12 | 12 | 数量匹配 |
| API 端点总数 | ~80 | ~50 | **62%** |
| 完全对齐 | — | — | 约 35 个端点 |
| URL 路径差异 | — | — | 全局单复数问题 |
| 完全缺失 | — | — | 约 30 个端点 |

### 全局差异

| 差异 | Java 后端 | Python 后端 |
|------|----------|------------|
| **Agent URL** | `/api/agent` (单数) | `/api/agents` (复数) |
| **Datasource URL** | `/api/datasource` (单数) | `/api/datasources` (复数) |
| **ModelConfig URL** | `/api/model-config` | `/api/model-configs` (复数) |
| **Knowledge URL** | `/api/agent-knowledge` + `/api/business-knowledge` (独立) | `/api/agents/{id}/knowledge` (嵌套) |
| **SemanticModel URL** | `/api/semantic-model` (独立) | `/api/agents/{id}/semantic-models` (嵌套) |
| **Chat URL** | `/api/agent/{id}/sessions`, `/api/sessions/...` (独立) | **完全缺失** |
| **响应包装** | 部分 `ApiResponse<T>`, 部分裸对象 | 全部裸对象 |

---

## 逐控制器对比

### 1. Agent 管理 (`/api/agent`)

| # | 方法 | Java 端点 | Python 端点 | 状态 |
|---|------|---------|------------|------|
| 1 | GET | `/api/agent/list?status=&keyword=` | `/api/agents?status=&skip=&limit=` | **路径+参数** |
| 2 | GET | `/api/agent/{id}` | `/api/agents/{id}` | **路径** |
| 3 | POST | `/api/agent` | `/api/agents` | **路径** |
| 4 | PUT | `/api/agent/{id}` | `/api/agents/{id}` | **路径** |
| 5 | DELETE | `/api/agent/{id}` | `/api/agents/{id}` | **路径** |
| 6 | POST | `/api/agent/{id}/publish` | `/api/agents/{id}/publish` | **路径** |
| 7 | POST | `/api/agent/{id}/offline` | `/api/agents/{id}/offline` | **路径** |
| 8 | GET | `/api/agent/{id}/api-key` | `/api/agent/{id}/api-key` | **对齐** ✅ |
| 9 | POST | `/api/agent/{id}/api-key/generate` | `/api/agent/{id}/api-key/generate` | **对齐** ✅ |
| 10 | POST | `/api/agent/{id}/api-key/reset` | `/api/agent/{id}/api-key/reset` | **对齐** ✅ |
| 11 | DELETE | `/api/agent/{id}/api-key` | `/api/agent/{id}/api-key` | **对齐** ✅ |
| 12 | POST | `/api/agent/{id}/api-key/enable?enabled=` | `/api/agent/{id}/api-key/enable?enabled=` | **对齐** ✅ |
| 13 | GET | `/api/agent/{id}/preset-questions` | `/api/agent/{id}/preset-questions` | **对齐** ✅ |
| 14 | POST | `/api/agent/{id}/preset-questions` | `/api/agent/{id}/preset-questions` | **对齐** ✅ |
| 15 | DELETE | `/api/agent/{id}/preset-questions/{qid}` | `/api/agent/{id}/preset-questions/{qid}` | **对齐** ✅ |

**所有 15 端点已对齐。** keyword 搜索参数 + list 子路径暂未对齐（Java 用 `/api/agent/list?keyword=`，Python 用 `/api/agent?status=`）。

---

### 2. Datasource 管理 (`/api/datasource`)

| # | 方法 | Java 端点 | Python 端点 | 状态 |
|---|------|---------|------------|------|
| 1 | GET | `/api/datasource/types` | `/api/datasources/types` | **路径+响应格式** |
| 2 | GET | `/api/datasource?status=&type=` | `/api/datasources?type=&skip=&limit=` | **路径** |
| 3 | GET | `/api/datasource/{id}` | `/api/datasources/{id}` | **路径** |
| 4 | GET | `/api/datasource/{id}/tables` | `/api/datasources/{id}/tables` | **路径** |
| 5 | POST | `/api/datasource` | `/api/datasources` | **路径** |
| 6 | PUT | `/api/datasource/{id}` | `/api/datasources/{id}` | **路径** |
| 7 | DELETE | `/api/datasource/{id}` | `/api/datasources/{id}` | **路径** |
| 8 | POST | `/api/datasource/{id}/test` | `/api/datasources/{id}/test` | **路径** |
| 9 | GET | `/api/datasource/{id}/tables/{tn}/columns` | `/api/datasources/{id}/tables/{tn}/columns` | **路径** |
| 10 | GET | `/api/datasource/{id}/logical-relations` | — | **缺失** |
| 11 | POST | `/api/datasource/{id}/logical-relations` | — | **缺失** |
| 12 | PUT | `/api/datasource/{id}/logical-relations/{rid}` | — | **缺失** |
| 13 | DELETE | `/api/datasource/{id}/logical-relations/{rid}` | — | **缺失** |
| 14 | PUT | `/api/datasource/{id}/logical-relations` (批量) | — | **缺失** |

**差距:** LogicalRelation CRUD (5 端点) + types 响应格式 + 字段名 `databaseName` — 共 **5 端点缺失**。

**types 响应差异:**
- Java: `ApiResponse<List<{code, typeName, dialect, protocol, displayName}>>` (6种数据库)
- Python: `[{value, label}]` (3种数据库)

---

### 3. Agent-Datasource 关联 (`/api/agent/{agentId}/datasources`)

| # | 方法 | Java 端点 | Python 端点 | 状态 |
|---|------|---------|------------|------|
| 1 | POST | `/api/agent/{id}/datasources/init` | — | **缺失** |
| 2 | GET | `/api/agent/{id}/datasources` | `/api/agents/{id}/datasources` | **路径** |
| 3 | GET | `/api/agent/{id}/datasources/active` | `/api/agents/{id}/datasources/active` | **路径** |
| 4 | POST | `/api/agent/{id}/datasources/{dsId}` | `/api/agents/{id}/datasources/{dsId}` | **路径** |
| 5 | POST | `/api/agent/{id}/datasources/tables` | — | **缺失** |
| 6 | DELETE | `/api/agent/{id}/datasources/{dsId}` | `/api/agents/{id}/datasources/{dsId}` | **路径** |
| 7 | PUT | `/api/agent/{id}/datasources/toggle` | `/api/agents/{id}/datasources/{dsId}/activate` (POST) | **路径+方法** |

**差距:** `init` (Schema初始化) + `tables` (表选择) + `toggle` 路径不同 — 共 **2 端点缺失**。

---

### 4. AgentKnowledge (`/api/agent-knowledge`)

| # | 方法 | Java 端点 | Python 端点 | 状态 |
|---|------|---------|------------|------|
| 1 | GET | `/api/agent-knowledge/{id}` | `/api/agents/{id}/knowledge/{kid}` | **路径完全不同** |
| 2 | POST | `/api/agent-knowledge/create` (multipart) | `/api/agents/{id}/knowledge` | **路径完全不同** |
| 3 | PUT | `/api/agent-knowledge/{id}` | `/api/agents/{id}/knowledge/{kid}` | **路径完全不同** |
| 4 | PUT | `/api/agent-knowledge/recall/{id}?isRecall=` | — | **缺失** |
| 5 | DELETE | `/api/agent-knowledge/{id}` | `/api/agents/{id}/knowledge/{kid}` | **路径完全不同** |
| 6 | POST | `/api/agent-knowledge/query/page` | — | **缺失** (分页查询) |
| 7 | POST | `/api/agent-knowledge/retry-embedding/{id}` | — | **缺失** |

**差距:** 整个 Knowledge API 路径体系不同。Java 使用独立 `/api/agent-knowledge`，Python 挂在 Agent 下面。Java 支持文件上传 (multipart)，Python 不支持。recall 状态切换、分页查询、向量化重试均缺失。

---

### 5. BusinessKnowledge (`/api/business-knowledge`)

| # | 方法 | Java 端点 | Python 端点 | 状态 |
|---|------|---------|------------|------|
| 1 | GET | `/api/business-knowledge?agentId=&keyword=` | — | **完全缺失** |
| 2 | GET | `/api/business-knowledge/{id}` | — | **完全缺失** |
| 3 | POST | `/api/business-knowledge` | — | **完全缺失** |
| 4 | PUT | `/api/business-knowledge/{id}` | — | **完全缺失** |
| 5 | DELETE | `/api/business-knowledge/{id}` | — | **完全缺失** |
| 6 | POST | `/api/business-knowledge/recall/{id}` | — | **完全缺失** |
| 7 | POST | `/api/business-knowledge/refresh-vector-store` | — | **完全缺失** |
| 8 | POST | `/api/business-knowledge/retry-embedding/{id}` | — | **完全缺失** |

**差距:** BusinessKnowledge 是 Java 版独立的知识类型 (业务术语)，Python 将其合并到 Knowledge 中。**8 端点完全缺失**。

---

### 6. SemanticModel (`/api/semantic-model`)

| # | 方法 | Java 端点 | Python 端点 | 状态 |
|---|------|---------|------------|------|
| 1 | GET | `/api/semantic-model?keyword=&agentId=` | `/api/agents/{id}/semantic-models` | **路径完全不同** |
| 2 | GET | `/api/semantic-model/{id}` | `/api/agents/{id}/semantic-models/{mid}` | **路径完全不同** |
| 3 | POST | `/api/semantic-model` | `/api/agents/{id}/semantic-models` | **路径完全不同** |
| 4 | PUT | `/api/semantic-model/{id}` | `/api/agents/{id}/semantic-models/{mid}` | **路径完全不同** |
| 5 | DELETE | `/api/semantic-model/{id}` | `/api/agents/{id}/semantic-models/{mid}` | **路径完全不同** |
| 6 | DELETE | `/api/semantic-model/batch` | — | **缺失** |
| 7 | PUT | `/api/semantic-model/enable` | — | **缺失** |
| 8 | PUT | `/api/semantic-model/disable` | — | **缺失** |
| 9 | POST | `/api/semantic-model/batch-import` | — | **缺失** |
| 10 | POST | `/api/semantic-model/import/excel` | — | **缺失** |
| 11 | GET | `/api/semantic-model/template/download` | — | **缺失** |

**差距:** 路径体系完全不同 + 6 个批量/Excel 操作缺失。Java 的 SemanticModel 是独立资源，Python 挂在 Agent 下。

---

### 7. Chat 会话 (`/api`)

| # | 方法 | Java 端点 | Python 端点 | 状态 |
|---|------|---------|------------|------|
| 1 | GET | `/api/agent/{id}/sessions` | `/api/agent/{id}/sessions` | **对齐** ✅ |
| 2 | POST | `/api/agent/{id}/sessions` | `/api/agent/{id}/sessions` | **对齐** ✅ |
| 3 | DELETE | `/api/agent/{id}/sessions` | `/api/agent/{id}/sessions` | **对齐** ✅ |
| 4 | GET | `/api/sessions/{id}/messages` | `/api/sessions/{id}/messages` | **对齐** ✅ |
| 5 | POST | `/api/sessions/{id}/messages` | `/api/sessions/{id}/messages` | **对齐** ✅ |
| 6 | PUT | `/api/sessions/{id}/pin?isPinned=` | `/api/sessions/{id}/pin?isPinned=` | **对齐** ✅ |
| 7 | PUT | `/api/sessions/{id}/rename?title=` | `/api/sessions/{id}/rename?title=` | **对齐** ✅ |
| 8 | DELETE | `/api/sessions/{id}` | `/api/sessions/{id}` | **对齐** ✅ |
| 9 | POST | `/api/sessions/{id}/reports/html` | `/api/sessions/{id}/reports/html` | **对齐** ✅ |

**所有 9 端点已实现。**

---

### 8. Graph 流式查询 (`/api`)

| # | 方法 | Java 端点 | Python 端点 | 状态 |
|---|------|---------|------------|------|
| 1 | GET | `/api/stream/search?agentId=&query=&threadId=&...` | `/api/stream/search` (GET) | **对齐** |
| — | POST | (无) | `/api/query/stream` (POST) | Python 额外提供 |

**参数对齐:**
| Java 参数 | Python 参数 | 状态 |
|-----------|------------|------|
| `agentId` | `agentId` | ✅ |
| `query` | `query` | ✅ |
| `threadId` | `threadId` | ✅ |
| `humanFeedback` | `humanFeedback` | ✅ |
| `humanFeedbackContent` | `humanFeedbackContent` | ✅ |
| `rejectedPlan` | `rejectedPlan` | ✅ |
| `nl2sqlOnly` | `nl2sqlOnly` | ✅ |

**SSE 事件类型:** Python 的 TextType 标记与 Java 的 TextType 枚举兼容 ✅。

---

### 9. ModelConfig (`/api/model-config`)

| # | 方法 | Java 端点 | Python 端点 | 状态 |
|---|------|---------|------------|------|
| 1 | GET | `/api/model-config/list` | `/api/model-configs` | **路径** |
| 2 | POST | `/api/model-config/add` | `/api/model-configs` | **路径** |
| 3 | PUT | `/api/model-config/update` | `/api/model-configs/{id}` | **路径+方法+参数** |
| 4 | DELETE | `/api/model-config/{id}` | `/api/model-configs/{id}` | **路径** |
| 5 | POST | `/api/model-config/activate/{id}` | `/api/model-configs/{id}/set-default` | **路径** |
| 6 | POST | `/api/model-config/test` | `/api/model-configs/{id}/test` | **路径+语义不同** |
| 7 | GET | `/api/model-config/check-ready` | `/api/model-configs/check-ready` | **路径+响应字段** |

**响应字段差异:**
- `check-ready`: Java `{chatModelReady, embeddingModelReady, ready}` → Python `{chatReady, embeddingReady, ready}` ❌

**ModelConfig DTO 字段 (Java 有，Python 缺):**
- `modelType` (CHAT/EMBEDDING)
- `maxTokens`
- `completionsPath`
- `embeddingsPath`
- `proxyEnabled`, `proxyHost`, `proxyPort`, `proxyUsername`, `proxyPassword`

---

### 10. FileUpload (`/api/upload`)

| # | 方法 | Java 端点 | Python 端点 | 状态 |
|---|------|---------|------------|------|
| 1 | POST | `/api/upload/avatar` | — | **完全缺失** |
| 2 | GET | `/api/upload/**` | — | **完全缺失** |

**差距:** 文件上传/访问能力完全缺失 — **2 端点缺失**。

---

## 差距汇总

### P0 — URL 路径系统性差异 (Phase 1 ✅ 已修复)

| 模块 | Java 路径 | Python 路径 (修复前) | Python 路径 (修复后) |
|------|----------|-------------------|-------------------|
| Agent | `/api/agent` | `/api/agents` | `/api/agent` ✅ |
| Datasource | `/api/datasource` | `/api/datasources` | `/api/datasource` ✅ |
| ModelConfig | `/api/model-config` | `/api/model-configs` | `/api/model-config` ✅ |
| SemanticModel | `/api/semantic-model` (独立) | `/api/agents/{id}/semantic-models` (嵌套) | 仍嵌套 (Phase 6) |
| Knowledge | `/api/agent-knowledge` (独立) | `/api/agents/{id}/knowledge` (嵌套) | 仍嵌套 (Phase 5) |

### P0 — 响应格式差异 (Phase 1 ✅ 已修复)

Java 大部分端点返回 `ApiResponse<T>` = `{success: bool, message: str, data: T}`。现已添加 `ApiResponseMiddleware` 全局中间件，自动包装所有 JSON 响应为此格式。异常处理器返回 `{success: false, ...}` 不会被重复包装。

### P1 — 完全缺失的控制器 (3 个)

| Java 控制器 | 缺失端点 | 模型是否已有 |
|------------|---------|-------------|
| ChatController | 9 | ✅ 已有 |
| BusinessKnowledgeController | 8 | ❌ 无独立模型 |
| FileUploadController | 2 | ❌ |

### P1 — 部分缺失的端点 (按模块)

| 模块 | 缺失功能 | 缺失数 |
|------|---------|--------|
| Agent | API Key 管理 (generate/reset/toggle) | 5 |
| Agent | PresetQuestion CRUD | 3 |
| Datasource | LogicalRelation CRUD | 5 |
| AgentDatasource | Schema init + Tables | 2 |
| AgentKnowledge | recall 状态 + 分页查询 + 向量化重试 | 3 |
| SemanticModel | 批量操作 + Excel | 6 |
| ModelConfig | 代理字段 + 路径 | 7 字段 |

---

## 修复计划

| 阶段 | 内容 | 端点/字段 | 影响 |
|------|------|----------|------|
| **1** | ~~统一 URL 前缀 + ApiResponse 包装~~ ✅ 完成 | 全局 | 解除所有 404 + 解析失败 |
| **2** | ~~Chat 会话 API (模型已有)~~ ✅ 完成 | 9 端点 | 对话历史核心功能 |
| **3** | ~~Agent API Key + PresetQuestion~~ ✅ 完成 | 8 端点 | Agent 管理完整 |
| **4** | LogicalRelation + Datasource Tables | 7 端点 | 数据源管理完整 |
| **5** | Knowledge/BusinessKnowledge 对齐 | 11 端点 | 知识库完整 |
| **6** | SemanticModel 批量操作 | 6 端点 | 语义模型完整 |
| **7** | ModelConfig 字段补全 + FileUpload | 7 字段 + 2 端点 | 配置管理完整 |

**总计: 约 30 个缺失端点 + 全局路径/响应差异需要修复。**
