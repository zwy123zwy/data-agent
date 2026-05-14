# Java DataAgent — 数据库表结构完全参考

> 对齐版本: `DataAgent/data-agent-management/src/main/resources/sql/schema.sql`
> 代码路径: `DataAgent/data-agent-management/src/main/java/com/alibaba/cloud/ai/dataagent/entity/`
> 数据访问方式: MyBatis annotation-based mapper（无 JPA、无 XML mapper）

---

## 概览

Java DataAgent 有 **13 张内部应用表**（存储在 `saa_data_agent` 数据库），外加 **11 张外部示例数据表**（用于 Agent 分析演示）。

### Python 对齐状态

| # | Java 表名 | 业务含义 | Python 状态 |
|---|----------|---------|------------|
| 1 | `agent` | 智能体定义 | ✅ 已有，缺 `human_review_enabled` 列 |
| 2 | `business_knowledge` | 业务知识（术语同义词） | ✅ 已有，缺 FK + 多个索引 |
| 3 | `semantic_model` | 语义模型（字段别名） | ✅ 已有，多了 `sample_values`/`metadata_` |
| 4 | `agent_knowledge` | 智能体知识（文档/QA） | ✅ 已有（命名 `knowledge.py`），多了 `embedding_id`/`metadata_`/`enabled` |
| 5 | `datasource` | 数据源连接配置 | ✅ 已有，缺 NOT NULL 约束 + 索引，列名不同 |
| 6 | `logical_relation` | 表间逻辑关系 | ✅ 已有，缺索引 |
| 7 | `agent_datasource` | Agent-数据源关联 | ✅ 已有，缺 UNIQUE + 索引，默认值不同 |
| 8 | `agent_preset_question` | Agent 预设问题 | ✅ 已有，缺索引 |
| 9 | `chat_session` | 会话 | ✅ 已有，缺索引 |
| 10 | `chat_message` | 消息 | ✅ 已有，缺索引 |
| 11 | `user_prompt_config` | 自定义 Prompt 配置 | ✅ 已有（命名 `prompt_config.py`），缺索引 |
| 12 | `agent_datasource_tables` | Agent 选定表清单 | ✅ 已有，缺 UNIQUE 约束 |
| 13 | `model_config` | LLM 模型配置 | ✅ 已有，完全匹配 |
| — | `human_feedback` | 人工反馈记录 | ❌ Java 无此表，Python 独占 |
| — | `query_plan` | 查询计划持久化 | ❌ Java 无此表，Python 独占 |
| — | `workflow_execution_metrics` | 执行指标收集 | ❌ Java 无此表，Python 独占 |
| — | `session_thread_mapping` | session↔thread 映射 | ❌ 两端均无，OpenSpec 建议新增 |

---

## 13 张内部表详文

### 1. `agent` — 智能体

每个 Agent 代表一个独立的数据分析助手实例，绑定特定的数据源、知识库、语义模型。

| 字段 | 类型 | 约束 | 含义 |
|-----|------|------|------|
| `id` | `INT` | PK, AUTO_INCREMENT | Agent 唯一标识 |
| `name` | `VARCHAR(255)` | NOT NULL | Agent 名称，前端展示 |
| `description` | `TEXT` | | Agent 描述，说明它能分析什么数据 |
| `avatar` | `TEXT` | | 头像 URL |
| `status` | `VARCHAR(50)` | DEFAULT `'draft'` | 发布状态: `draft` / `published` / `offline` |
| `api_key` | `VARCHAR(255)` | DEFAULT NULL | API Key，格式 `sk-xxx`，用于外部调用鉴权 |
| `api_key_enabled` | `TINYINT` | DEFAULT 0 | API Key 是否启用: 0=禁用, 1=启用 |
| `prompt` | `TEXT` | | 自定义 system prompt，覆盖默认行为 |
| `category` | `VARCHAR(100)` | | Agent 分类，用于前端分组展示 |
| `admin_id` | `BIGINT` | | 管理员/创建者用户 ID |
| `tags` | `TEXT` | | 逗号分隔的标签列表 |
| `create_time` | `TIMESTAMP` | DEFAULT CURRENT_TIMESTAMP | 创建时间 |
| `update_time` | `TIMESTAMP` | ON UPDATE CURRENT_TIMESTAMP | 最后修改时间 |

**索引**: `idx_name`(name), `idx_status`(status), `idx_category`(category), `idx_admin_id`(admin_id)

**Python 差异**:
- Python 多了 `human_review_enabled` (Integer, default=0) 字段，Java agent 表无此列（Java 通过请求参数 `humanFeedback` 控制，不存储在 agent 表中）
- Python 的 `String(100)` 对应 Java 的 `VARCHAR(255)`，长度不一致
- Python 缺少 4 个索引

---

### 2. `business_knowledge` — 业务知识

存储业务术语的同义词映射和描述，帮助 LLM 理解用户问题中的业务术语（如 "GMV" → "总销售额"）。

| 字段 | 类型 | 约束 | 含义 |
|-----|------|------|------|
| `id` | `INT` | PK, AUTO_INCREMENT | 主键 |
| `business_term` | `VARCHAR(255)` | NOT NULL | 业务术语，如 "客单价" |
| `description` | `TEXT` | | 术语解释，注入 LLM prompt |
| `synonyms` | `TEXT` | | 逗号分隔的同义词，如 "每客户平均消费,ARPU" |
| `is_recall` | `INT` | DEFAULT 1 | 是否参与召回: 0=否, 1=是 |
| `agent_id` | `INT` | NOT NULL, FK→agent(id) | 所属 Agent |
| `created_time` | `TIMESTAMP` | DEFAULT CURRENT_TIMESTAMP | |
| `updated_time` | `TIMESTAMP` | ON UPDATE CURRENT_TIMESTAMP | |
| `embedding_status` | `VARCHAR(20)` | DEFAULT NULL | 向量化状态: `PENDING`/`PROCESSING`/`COMPLETED`/`FAILED` |
| `error_msg` | `VARCHAR(255)` | DEFAULT NULL | 向量化失败的错误信息 |
| `is_deleted` | `INT` | DEFAULT 0 | 逻辑删除标记: 0=正常, 1=已删除 |

**索引**: `idx_business_term`(business_term), `idx_agent_id`(agent_id), `idx_is_recall`(is_recall), `idx_embedding_status`(embedding_status), `idx_is_deleted`(is_deleted)

**外键**: `agent_id` REFERENCES `agent(id)` ON DELETE CASCADE

**Python 差异**:
- 缺少 5 个索引中的 4 个（仅有 `idx_agent_id`）
- 缺少 FK 约束

---

### 3. `semantic_model` — 语义模型

定义数据表字段的业务别名和描述，让 LLM 将用户的自然语言（如 "销售额"）映射到物理列名（如 `total_amount`）。

| 字段 | 类型 | 约束 | 含义 |
|-----|------|------|------|
| `id` | `INT(11)` | PK, AUTO_INCREMENT | |
| `agent_id` | `INT(11)` | NOT NULL, FK→agent(id) | |
| `datasource_id` | `INT(11)` | NOT NULL | 数据源 ID |
| `table_name` | `VARCHAR(255)` | NOT NULL | 物理表名 |
| `column_name` | `VARCHAR(255)` | NOT NULL, DEFAULT `''` | 物理列名 |
| `business_name` | `VARCHAR(255)` | NOT NULL, DEFAULT `''` | 业务别名，如 "销售金额" |
| `synonyms` | `TEXT` | | 逗号分隔的同义词 |
| `business_description` | `TEXT` | | 列的详细业务含义，注入 LLM prompt |
| `column_comment` | `VARCHAR(255)` | DEFAULT NULL | 数据库原始列注释 |
| `data_type` | `VARCHAR(255)` | NOT NULL, DEFAULT `''` | 列的数据类型，如 `int`, `varchar(20)` |
| `status` | `TINYINT(4)` | NOT NULL, DEFAULT 1 | 0=禁用, 1=启用 |
| `created_time` | `TIMESTAMP` | NOT NULL, DEFAULT CURRENT_TIMESTAMP | |
| `updated_time` | `TIMESTAMP` | NOT NULL, ON UPDATE CURRENT_TIMESTAMP | |

**索引**: `idx_agent_id`(agent_id), `idx_field_name`(business_name), `idx_status`(status)

**Python 差异**:
- 多了 `sample_values`(JSON) — 存储列的样本数据值（Python 扩展）
- 多了 `metadata_`(JSON) — 存储额外元数据（Python 扩展）
- 缺少 `idx_field_name` 和 `idx_status` 索引
- `column_name` 在 Python 中可为 nullable，Java 中 NOT NULL DEFAULT ''

---

### 4. `agent_knowledge` — 智能体知识

存储上传到 Agent 的文档（PDF/Markdown）和 QA 问答对，是 RAG 检索的主要数据源。文档通过文本分割后向量化存入 Chroma。

| 字段 | 类型 | 约束 | 含义 |
|-----|------|------|------|
| `id` | `INT(11)` | PK, AUTO_INCREMENT | |
| `agent_id` | `INT(11)` | NOT NULL | 所属 Agent |
| `title` | `VARCHAR(255)` | NOT NULL | 知识标题 |
| `type` | `VARCHAR(50)` | NOT NULL | 知识类型: `DOCUMENT`(文档), `QA`(问答), `FAQ`(常见问题) |
| `question` | `TEXT` | | QA/FAQ 的问题（DOCUMENT 类型为 NULL） |
| `content` | `MEDIUMTEXT` | | QA/FAQ 的答案；DOCUMENT 的原始文本内容 |
| `is_recall` | `INT(11)` | DEFAULT 1 | 是否参与 RAG 召回: 0=否, 1=是 |
| `embedding_status` | `VARCHAR(20)` | DEFAULT NULL | 向量化状态: `PENDING`→`PROCESSING`→`COMPLETED`/`FAILED` |
| `error_msg` | `VARCHAR(255)` | DEFAULT NULL | 向量化失败原因 |
| `source_filename` | `VARCHAR(500)` | DEFAULT NULL | 上传的源文件名称 |
| `file_path` | `VARCHAR(500)` | DEFAULT NULL | 服务端存储路径 |
| `file_size` | `BIGINT(20)` | DEFAULT NULL | 文件大小（字节） |
| `file_type` | `VARCHAR(255)` | DEFAULT NULL | 文件格式: `pdf`, `md`, `markdown`, `doc` |
| `splitter_type` | `VARCHAR(50)` | DEFAULT `'token'` | 文本分割策略: `token`/`recursive`/`sentence`/`semantic` |
| `created_time` | `TIMESTAMP` | NOT NULL, DEFAULT CURRENT_TIMESTAMP | |
| `updated_time` | `TIMESTAMP` | NOT NULL, ON UPDATE CURRENT_TIMESTAMP | |
| `is_deleted` | `INT(11)` | DEFAULT 0 | 逻辑删除标记 |
| `is_resource_cleaned` | `INT(11)` | DEFAULT 0 | 物理资源是否清理: 0=未清理, 1=已清理向量+文件 |

**索引**: `idx_agent_id_status`(agent_id, is_recall), `idx_embedding_status`(embedding_status), `idx_is_deleted`(is_deleted)

**Python 差异**:
- Python 多了 `embedding_id`(String(100)) — Chroma 向量 ID（Java 可能在其他地方管理）
- Python 多了 `metadata_`(JSON) — 额外元数据
- Python 多了 `enabled`(Integer, default=1) — 启用/禁用开关（Java 无此字段）
- Python 的 `error_msg` 用 `Text`（无上限），Java 用 `VARCHAR(255)`

---

### 5. `datasource` — 数据源

存储可连接的外部数据库信息，Agent 通过关联的数据源获取业务数据。

| 字段 | 类型 | 约束 | 含义 |
|-----|------|------|------|
| `id` | `INT` | PK, AUTO_INCREMENT | |
| `name` | `VARCHAR(255)` | NOT NULL | 数据源名称 |
| `type` | `VARCHAR(50)` | NOT NULL | 数据库类型: `mysql` / `postgresql` |
| `host` | `VARCHAR(255)` | NOT NULL | 主机地址 |
| `port` | `INT` | NOT NULL | 端口号 |
| `database_name` | `VARCHAR(255)` | NOT NULL | 数据库名 |
| `username` | `VARCHAR(255)` | NOT NULL | 用户名 |
| `password` | `VARCHAR(255)` | NOT NULL | 密码（加密存储） |
| `connection_url` | `VARCHAR(1000)` | | 完整 JDBC URL |
| `status` | `VARCHAR(50)` | DEFAULT `'inactive'` | 状态: `active` / `inactive` |
| `test_status` | `VARCHAR(50)` | DEFAULT `'unknown'` | 连接测试结果: `success` / `failed` / `unknown` |
| `description` | `TEXT` | | 描述 |
| `creator_id` | `BIGINT` | | 创建者用户 ID |
| `create_time` | `TIMESTAMP` | DEFAULT CURRENT_TIMESTAMP | |
| `update_time` | `TIMESTAMP` | ON UPDATE CURRENT_TIMESTAMP | |

**索引**: `idx_name`(name), `idx_type`(type), `idx_status`(status), `idx_creator_id`(creator_id)

**Python 差异 (严重)**:
- **列名不同**: Python 的列名是 `database`，Java 是 `database_name`
- **默认值不同**: Python `status` 默认 `"active"`，Java 默认 `"inactive"`；Python `test_status` 默认 `"untested"`，Java 默认 `"unknown"`
- **NOT NULL 缺失**: Python 的 `host`/`port`/`username`/`password` 为 `Optional`（可为 NULL），Java 中均为 NOT NULL
- Python 缺少全部 4 个索引

---

### 6. `logical_relation` — 表间逻辑关系

手工定义的业务级表关联关系，帮助 LLM 在生成 SQL 时正确 JOIN 多张表。

| 字段 | 类型 | 约束 | 含义 |
|-----|------|------|------|
| `id` | `INT` | PK, AUTO_INCREMENT | |
| `datasource_id` | `INT` | NOT NULL, FK→datasource(id) | |
| `source_table_name` | `VARCHAR(100)` | NOT NULL | 源表名，如 `orders` |
| `source_column_name` | `VARCHAR(100)` | NOT NULL | 源表关联列，如 `user_id` |
| `target_table_name` | `VARCHAR(100)` | NOT NULL | 目标表名，如 `users` |
| `target_column_name` | `VARCHAR(100)` | NOT NULL | 目标表关联列，如 `id` |
| `relation_type` | `VARCHAR(20)` | DEFAULT NULL | 关系类型: `1:1` / `1:N` / `N:1` |
| `description` | `VARCHAR(500)` | DEFAULT NULL | 业务含义描述，注入 LLM prompt |
| `is_deleted` | `TINYINT(1)` | DEFAULT 0 | 逻辑删除标记 |
| `created_time` | `DATETIME` | DEFAULT CURRENT_TIMESTAMP | |
| `updated_time` | `DATETIME` | ON UPDATE CURRENT_TIMESTAMP | |

**索引**: `idx_datasource_id`(datasource_id), `idx_source_table`(datasource_id, source_table_name)—复合索引

**外键**: `datasource_id` REFERENCES `datasource(id)` ON DELETE CASCADE

**Python 差异**: 缺少全部 2 个索引；`description` 用 `Text`（无上限）vs Java `VARCHAR(500)`

---

### 7. `agent_datasource` — Agent-数据源关联

N:N 关联表，一个 Agent 可绑定多个数据源，一个数据源可被多个 Agent 使用。`is_active` 标记当前激活的数据源（每次查询只用激活的数据源）。

| 字段 | 类型 | 约束 | 含义 |
|-----|------|------|------|
| `id` | `INT` | PK, AUTO_INCREMENT | |
| `agent_id` | `INT` | NOT NULL, FK→agent(id) | Agent ID |
| `datasource_id` | `INT` | NOT NULL, FK→datasource(id) | 数据源 ID |
| `is_active` | `TINYINT` | DEFAULT 0 | 是否激活: 0=否, 1=是（一个 Agent 只能有一个激活的数据源） |
| `create_time` | `TIMESTAMP` | DEFAULT CURRENT_TIMESTAMP | |
| `update_time` | `TIMESTAMP` | ON UPDATE CURRENT_TIMESTAMP | |

**索引**: `uk_agent_datasource` UNIQUE (agent_id, datasource_id), `idx_agent_id`(agent_id), `idx_datasource_id`(datasource_id), `idx_is_active`(is_active)

**Python 差异 (严重)**:
- **`is_active` 默认值不兼容**: Python `default=1` (激活)，Java `DEFAULT 0` (不激活)
- **缺少 UNIQUE 约束**: Python 无 `UNIQUE(agent_id, datasource_id)`，可能导致同一 Agent 重复绑定同一数据源
- 缺少 3 个单独索引

---

### 8. `agent_preset_question` — Agent 预设问题

存储每个 Agent 的推荐问题列表，前端在 Agent 输入框下方展示，用户点击即可快速提问。

| 字段 | 类型 | 约束 | 含义 |
|-----|------|------|------|
| `id` | `INT` | PK, AUTO_INCREMENT | |
| `agent_id` | `INT` | NOT NULL, FK→agent(id) | |
| `question` | `TEXT` | NOT NULL | 预设问题文本 |
| `sort_order` | `INT` | DEFAULT 0 | 排序权重，值越小越靠前 |
| `is_active` | `TINYINT` | DEFAULT 0 | 0=禁用, 1=启用 |
| `create_time` | `TIMESTAMP` | DEFAULT CURRENT_TIMESTAMP | |
| `update_time` | `TIMESTAMP` | ON UPDATE CURRENT_TIMESTAMP | |

**Python 差异**: 缺少 `idx_agent_id`, `idx_sort_order`, `idx_is_active` 索引

---

### 9. `chat_session` — 会话

存储用户与 Agent 的对话会话，每打开一次新的分析对话即创建一个 session。

| 字段 | 类型 | 约束 | 含义 |
|-----|------|------|------|
| `id` | `VARCHAR(36)` | PK (UUID) | 会话 ID，UUID 字符串 |
| `agent_id` | `INT` | NOT NULL, FK→agent(id) | 所属 Agent |
| `title` | `VARCHAR(255)` | DEFAULT `'new conversation'` | 会话标题（LLM 根据首条消息自动生成） |
| `status` | `VARCHAR(50)` | DEFAULT `'active'` | 状态: `active` / `archived` / `deleted` |
| `is_pinned` | `TINYINT` | DEFAULT 0 | 是否置顶: 0=否, 1=是 |
| `user_id` | `BIGINT` | | 所属用户 ID |
| `create_time` | `TIMESTAMP` | DEFAULT CURRENT_TIMESTAMP | |
| `update_time` | `TIMESTAMP` | ON UPDATE CURRENT_TIMESTAMP | |

**索引**: `idx_agent_id`(agent_id), `idx_user_id`(user_id), `idx_status`(status), `idx_is_pinned`(is_pinned), `idx_create_time`(create_time)

**Python 差异**: 缺少全部 5 个索引

---

### 10. `chat_message` — 消息

存储会话中的每条消息，包括用户问题和 Assistant 回复（含 SQL、分析结果、报告等）。

| 字段 | 类型 | 约束 | 含义 |
|-----|------|------|------|
| `id` | `BIGINT` | PK, AUTO_INCREMENT | 消息唯一 ID |
| `session_id` | `VARCHAR(36)` | NOT NULL, FK→chat_session(id) | 所属会话 ID |
| `role` | `VARCHAR(20)` | NOT NULL | 角色: `user` / `assistant` / `system` |
| `content` | `TEXT` | NOT NULL | 消息正文 |
| `message_type` | `VARCHAR(50)` | DEFAULT `'text'` | 消息类型: `text` / `sql` / `result` / `error` / `html` / `markdown` / `python` |
| `metadata` | `JSON` | | 附加元数据（自由 JSON） |
| `create_time` | `TIMESTAMP` | DEFAULT CURRENT_TIMESTAMP | 消息发送时间 |

**索引**: `idx_session_id`(session_id), `idx_role`(role), `idx_message_type`(message_type), `idx_create_time`(create_time)

**Python 差异**: 缺少全部 4 个索引；Python 用 `metadata_`（下划线后缀）列名

---

### 11. `user_prompt_config` — 自定义 Prompt 配置

per-Agent 的系统提示词优化配置。支持按 `prompt_type`（如 `planner`, `report-generator`）追加自定义 prompt。`agent_id` 为 NULL 时表示全局默认配置。

| 字段 | 类型 | 约束 | 含义 |
|-----|------|------|------|
| `id` | `VARCHAR(36)` | PK (UUID) | 配置 ID |
| `name` | `VARCHAR(255)` | NOT NULL | 配置名称，如 "销售报告模板" |
| `prompt_type` | `VARCHAR(100)` | NOT NULL | 目标节点类型: `planner`/`report-generator`/`sql-generate`/`intent`/`feasibility`/`knowledge-recall`/`schema-recall`/`python-generate`/`sql-consistency` |
| `agent_id` | `INT` | NULL=全局配置 | 指定 Agent 时生效，NULL 时为全局 |
| `system_prompt` | `TEXT` | NOT NULL | 追加到默认 prompt 后的自定义指令 |
| `enabled` | `TINYINT` | DEFAULT 1 | 0=禁用, 1=启用 |
| `description` | `TEXT` | | 配置说明 |
| `priority` | `INT` | DEFAULT 0 | 优先级，值越大越优先（同 prompt_type 多条时选择 priority 最高的） |
| `display_order` | `INT` | DEFAULT 0 | 前端展示排序，值越小越靠前 |
| `create_time` | `TIMESTAMP` | DEFAULT CURRENT_TIMESTAMP | |
| `update_time` | `TIMESTAMP` | ON UPDATE CURRENT_TIMESTAMP | |
| `creator` | `VARCHAR(255)` | | 创建人 |

**索引**: `idx_prompt_type`(prompt_type), `idx_agent_id`(agent_id), `idx_enabled`(enabled), `idx_create_time`(create_time), `idx_prompt_type_enabled_priority`(prompt_type, agent_id, enabled, priority DESC)—复合优先级索引, `idx_display_order`(display_order ASC)

**Python 差异**: 缺少 6 个索引中的 4 个；`system_prompt` 在 Python 中为 Optional（可为 NULL），Java 中 NOT NULL

---

### 12. `agent_datasource_tables` — Agent 选定表

记录 Agent-数据源关联下用户勾选了哪些表参与分析。`select_tables` 字段限制 Agent 只能看到这些表。

| 字段 | 类型 | 约束 | 含义 |
|-----|------|------|------|
| `id` | `INT` | PK, AUTO_INCREMENT | |
| `agent_datasource_id` | `INT` | NOT NULL, FK→agent_datasource(id) | Agent-数据源关联 ID |
| `table_name` | `VARCHAR(255)` | NOT NULL | 选中的表名 |
| `create_time` | `TIMESTAMP` | DEFAULT CURRENT_TIMESTAMP | |
| `update_time` | `TIMESTAMP` | DEFAULT CURRENT_TIMESTAMP | |

**索引**: `UNIQUE(agent_datasource_id, table_name)` — 同一关联下不允许重复表

**外键**: `agent_datasource_id` REFERENCES `agent_datasource(id)` ON UPDATE CASCADE ON DELETE CASCADE

**Python 差异**: 缺少 UNIQUE 约束（可能插入重复表）

---

### 13. `model_config` — LLM 模型配置

管理 LLM 和 Embedding 模型的连接信息，支持代理配置。

| 字段 | 类型 | 约束 | 含义 |
|-----|------|------|------|
| `id` | `INT(11)` | PK, AUTO_INCREMENT | |
| `provider` | `VARCHAR(255)` | NOT NULL | 模型提供商，如 `openai`/`deepseek`/`qwen` |
| `base_url` | `VARCHAR(255)` | NOT NULL | API 地址 |
| `api_key` | `VARCHAR(255)` | NOT NULL | API Key |
| `model_name` | `VARCHAR(255)` | NOT NULL | 模型名，如 `deepseek-v4-flash` |
| `temperature` | `DECIMAL(10,2) UNSIGNED` | DEFAULT 0.00 | 温度参数 [0, 2] |
| `is_active` | `TINYINT(1)` | DEFAULT 0 | 是否启用 |
| `max_tokens` | `INT(11)` | DEFAULT 2000 | 最大输出 token 数 |
| `model_type` | `VARCHAR(20)` | NOT NULL, DEFAULT `'CHAT'` | 模型类型: `CHAT` / `EMBEDDING` |
| `completions_path` | `VARCHAR(255)` | DEFAULT NULL | API 补全路径，如 `/v1/chat/completions` |
| `embeddings_path` | `VARCHAR(255)` | DEFAULT NULL | API 嵌入路径，如 `/v1/embeddings` |
| `created_time` | `DATETIME` | DEFAULT NULL | |
| `updated_time` | `DATETIME` | DEFAULT NULL | |
| `is_deleted` | `INT(11)` | DEFAULT 0 | 逻辑删除 |
| `proxy_enabled` | `TINYINT(1)` | DEFAULT 0 | 是否启用代理 |
| `proxy_host` | `VARCHAR(255)` | DEFAULT NULL | 代理主机 |
| `proxy_port` | `INT(11)` | DEFAULT NULL | 代理端口 |
| `proxy_username` | `VARCHAR(255)` | DEFAULT NULL | 代理用户名 |
| `proxy_password` | `VARCHAR(255)` | DEFAULT NULL | 代理密码 |

**索引**: 仅 PRIMARY KEY

**Python 差异**: Python 完全匹配，无差异

---

## Python 独占的 3 张表

这些表在 Python 项目中有定义，但 Java 项目不存在对应表：

### `human_feedback` — 人工反馈记录
Python 自己的扩展表，用于持久化 HumanFeedback 的审批记录。

### `query_plan` — 查询计划持久化
Python 自己的扩展表，用于持久化 Planner 生成的执行计划 JSON。

### `workflow_execution_metrics` — 执行指标
Python 自己的扩展表，用于 Phase 7 的可观测性指标收集。

---

## 需要新增的表（两端均无）

### `session_thread_mapping`
OpenSpec `add-memory-system-and-production-engineering` 建议新增，用于统一 `session_id` 和 `thread_id`:

| 字段 | 类型 | 约束 | 含义 |
|-----|------|------|------|
| `id` | `INT` | PK, AUTO_INCREMENT | |
| `session_id` | `VARCHAR(36)` | NOT NULL, INDEXED | ChatSession 的 UUID |
| `thread_id` | `VARCHAR(36)` | NOT NULL, INDEXED | LangGraph checkpointer 的 thread_id |
| `agent_id` | `INT` | NOT NULL, FK→agent(id) | |
| `create_time` | `TIMESTAMP` | DEFAULT CURRENT_TIMESTAMP | |

**索引**: `INDEX idx_session_id(session_id)`, `INDEX idx_thread_id(thread_id)`, `UNIQUE(session_id)`
