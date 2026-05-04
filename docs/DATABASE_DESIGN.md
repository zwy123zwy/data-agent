# 数据库 E-R 设计文档

> 基于 Java DataAgent `schema.sql` 和全部 12 个 Entity 类逆向生成，覆盖 **14 张表** 及所有外键关系。

---

## 完整 E-R 图

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│                                                                                      │
│   ★ 图例:  ──<  = 1:N (一对多)    >── = N:1 (多对一)    ═══  = 双线核心实体          │
│                                                                                      │
│   ┌──────────────────────────────────────────────────────────────────────────────┐   │
│   │                         独立表 (无外键依赖)                                    │   │
│   │                                                                              │   │
│   │  ┌──────────────────────┐          ┌──────────────────────────────────┐      │   │
│   │  │    model_config      │          │       human_feedback             │      │   │
│   │  │  (LLM/Embedding 模型) │          │  (人工反馈, Python 扩展)          │      │   │
│   │  │  id | provider       │          │  id | thread_id | feedback_type  │      │   │
│   │  │  base_url | api_key  │          │  content | status | agent_id     │      │   │
│   │  │  model_name | type   │          └──────────────────────────────────┘      │   │
│   │  └──────────────────────┘                                                    │   │
│   └──────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                      │
│   ┌──────────────────────────────────────────────────────────────────────────────┐   │
│   │                    以 agent 为核心的第一层子表 (N:1 → agent)                    │   │
│   │                                                                              │   │
│   │  ┌──────────────────────┐  ┌──────────────────────┐  ┌────────────────────┐ │   │
│   │  │  business_knowledge  │  │   agent_knowledge    │  │  semantic_model    │ │   │
│   │  │  业务名词/同义词/RAG  │  │  知识文档/QA/FAQ     │  │  字段别名/业务语义  │ │   │
│   │  │  agent_id → agent    │  │  agent_id → agent    │  │  agent_id → agent  │ │   │
│   │  └──────────────────────┘  └──────────────────────┘  │  ds_id → datasource│ │   │
│   │                                                       └────────────────────┘ │   │
│   │  ┌──────────────────────┐  ┌──────────────────────┐  ┌────────────────────┐ │   │
│   │  │ agent_preset_question│  │    chat_session      │  │ user_prompt_config │ │   │
│   │  │  预设问题             │  │  对话会话             │  │  自定义 Prompt      │ │   │
│   │  │  agent_id → agent    │  │  agent_id → agent    │  │  agent_id → agent  │ │   │
│   │  └──────────────────────┘  └──────────┬───────────┘  │    (nullable)      │ │   │
│   │                                       │               └────────────────────┘ │   │
│   └───────────────────────────────────────┼───────────────────────────────────────┘   │
│                                           │                                           │
│                                           │ 1:N (session_id)                          │
│                                           ▼                                           │
│                               ┌──────────────────────┐                                │
│                               │    chat_message      │                                │
│                               │  消息 (user/assistant)│                                │
│                               │  session_id → session │                                │
│                               │  role | content | type│                                │
│                               └──────────────────────┘                                │
│                                                                                      │
│   ┌──────────────────────────────────────────────────────────────────────────────┐   │
│   │                         双核心 + 桥接层                                       │   │
│   │                                                                              │   │
│   │                         ┌──────────────────────────┐                          │   │
│   │                         │ agent_datasource_tables  │                          │   │
│   │                         │ 该关联下选中的数据表       │                          │   │
│   │                         │ agent_ds_id → agent_ds   │                          │   │
│   │                         └───────────┬──────────────┘                          │   │
│   │                                     │ N:1                                    │   │
│   │                                     │ agent_datasource_id                    │   │
│   ╞═════════════════════════════════════╪════════════════════════════════════════╡   │
│   │                                     ▼                                        │   │
│   │  ╔══════════════════╗    ┌──────────────────────────┐    ╔══════════════════╗│   │
│   │  ║     agent        ║    │   agent_datasource      │    ║   datasource     ║│   │
│   │  ║  (智能体)         ║◄───│  (M:N 桥接关联表)        │───►║  (数据源)         ║│   │
│   │  ║  id | name       ║1:N │  id | agent_id (FK)    │N:1 ║  id | name       ║│   │
│   │  ║  status | api_key║    │  datasource_id (FK)    │    ║  type | host      ║│   │
│   │  ║  prompt | tags   ║    │  is_active             │    ║  db | user/pass   ║│   │
│   │  ╚══════╤═══════════╝    └──────────────────────────┘    ╚══════╤═══════════╝│   │
│   │         │                                                        │          │   │
│   └─────────┼────────────────────────────────────────────────────────┼──────────┘   │
│             │                                                        │              │
│             │ 1:N (agent_id)                              1:N (datasource_id)        │
│             │  ┌─────────────────────────────────────┐     │              │
│             ├─►│ business_knowledge / agent_knowledge│     │              │
│             │  │ semantic_model / preset_question    │     │              │
│             │  │ chat_session / user_prompt_config   │     │              │
│             │  └─────────────────────────────────────┘     │              │
│             │                                               ▼              │
│             │                                  ┌──────────────────────┐   │
│             │                                  │  logical_relation    │   │
│             │                                  │  逻辑外键配置         │   │
│             │                                  │  datasource_id → ds  │   │
│             │                                  │  source_table.column  │   │
│             │                                  │  → target_table.column│   │
│             │                                  └──────────────────────┘   │
│             │                                                                         │
│             │  semantic_model 同时关联 agent_id 和 datasource_id:                     │
│             │  ┌─────────────────────────────────────────────────────┐                │
│             │  │        semantic_model                               │                │
│             │  │  agent_id ──► agent      (通过哪个 Agent 配置)       │                │
│             │  │  datasource_id ──► datasource (来自哪个数据源)       │                │
│             │  │  table_name + column_name → business_name + synonyms│                │
│             │  └─────────────────────────────────────────────────────┘                │
│             │                                                                         │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 全部 14 张表及外键关系

### 一、核心实体 (2 张)

| # | 表名 | 用途 | 主键 |
|---|------|------|------|
| 1 | **agent** | 智能体，整个系统的根实体 | `id` INT AUTO_INCREMENT |
| 2 | **datasource** | 数据源连接信息 (MySQL/PostgreSQL) | `id` INT AUTO_INCREMENT |

### 二、桥接关联 (2 张)

| # | 表名 | 用途 | 外键 |
|---|------|------|------|
| 3 | **agent_datasource** | Agent ↔ Datasource 的 M:N 关联，带 `is_active` 激活标记 | `agent_id` → agent, `datasource_id` → datasource |
| 4 | **agent_datasource_tables** | 某个 Agent-DataSource 关联下用户勾选的具体表名 | `agent_datasource_id` → agent_datasource |

```
agent ──< agent_datasource >── datasource
                  │
                  └──< agent_datasource_tables
```

### 三、第一层子表：挂载在 agent 下 (6 张)

| # | 表名 | 用途 | 外键 |
|---|------|------|------|
| 5 | **business_knowledge** | 业务名词/同义词/描述，RAG 向量检索的基础语料 | `agent_id` → agent |
| 6 | **agent_knowledge** | 知识源管理 (文档/QA/FAQ)，支持文件上传+向量化 | `agent_id` → agent |
| 7 | **semantic_model** | 数据库字段到业务语义的映射 (字段别名) | `agent_id` → agent, `datasource_id` → datasource |
| 8 | **agent_preset_question** | Agent 预设问题，展示在前端对话框的快捷提问 | `agent_id` → agent |
| 9 | **chat_session** | 聊天会话，记录每次对话的标题和状态 | `agent_id` → agent |
| 10 | **user_prompt_config** | 用户自定义 Prompt 配置，按 Agent+类型多维度生效 | `agent_id` → agent (nullable) |

```
agent ──< business_knowledge
agent ──< agent_knowledge
agent ──< semantic_model ──> datasource
agent ──< agent_preset_question
agent ──< chat_session
agent ──< user_prompt_config   (agent_id 可为 NULL，表示全局配置)
```

### 四、第二层子表 (1 张)

| # | 表名 | 用途 | 外键 |
|---|------|------|------|
| 11 | **chat_message** | 聊天消息，记录 user/assistant/system 的每一条消息 | `session_id` → chat_session |

```
chat_session ──< chat_message
```

### 五、挂载在 datasource 下 (1 张)

| # | 表名 | 用途 | 外键 |
|---|------|------|------|
| 12 | **logical_relation** | 逻辑外键配置，定义数据源中表之间的隐式关联 | `datasource_id` → datasource |

```
datasource ──< logical_relation
```

### 六、独立表 (2 张)

| # | 表名 | 用途 | 说明 |
|---|------|------|------|
| 13 | **model_config** | LLM/Embedding 模型配置 (provider/base_url/api_key) | 全局配置，不关联任何实体 |
| 14 | **human_feedback** | 人工反馈记录 (Python 扩展) | `agent_id` → agent (可选) |

---

## 外键依赖链 (从根到叶)

```
agent (根)
  ├── agent_datasource ──> datasource
  │       └── agent_datasource_tables
  ├── business_knowledge
  ├── agent_knowledge
  ├── semantic_model ──> datasource
  ├── agent_preset_question
  ├── chat_session
  │       └── chat_message
  └── user_prompt_config (nullable FK)

datasource (根)
  ├── agent_datasource ──> agent
  │       └── agent_datasource_tables
  ├── semantic_model ──> agent
  └── logical_relation

model_config (独立)
human_feedback (独立, Python 扩展)
```

---

## 各表 DDL 摘要

### agent
```sql
CREATE TABLE agent (
    id INT NOT NULL AUTO_INCREMENT,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    avatar TEXT,
    status VARCHAR(50) DEFAULT 'draft',          -- draft | published | offline
    api_key VARCHAR(255) DEFAULT NULL,            -- sk-xxx
    api_key_enabled TINYINT DEFAULT 0,
    prompt TEXT,                                   -- 自定义 Prompt
    category VARCHAR(100),
    admin_id BIGINT,
    tags TEXT,                                     -- 逗号分隔
    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id)
) ENGINE=InnoDB;
```

### datasource
```sql
CREATE TABLE datasource (
    id INT NOT NULL AUTO_INCREMENT,
    name VARCHAR(255) NOT NULL,
    type VARCHAR(50) NOT NULL,                     -- mysql | postgresql
    host VARCHAR(255) NOT NULL,
    port INT NOT NULL,
    database_name VARCHAR(255) NOT NULL,
    username VARCHAR(255) NOT NULL,
    password VARCHAR(255) NOT NULL,                -- 加密存储
    connection_url VARCHAR(1000),
    status VARCHAR(50) DEFAULT 'inactive',
    test_status VARCHAR(50) DEFAULT 'unknown',     -- success | failed | unknown
    description TEXT,
    creator_id BIGINT,
    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id)
) ENGINE=InnoDB;
```

### agent_datasource (M:N 桥接)
```sql
CREATE TABLE agent_datasource (
    id INT NOT NULL AUTO_INCREMENT,
    agent_id INT NOT NULL,
    datasource_id INT NOT NULL,
    is_active TINYINT DEFAULT 0,
    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_agent_datasource (agent_id, datasource_id),
    FOREIGN KEY (agent_id) REFERENCES agent(id) ON DELETE CASCADE,
    FOREIGN KEY (datasource_id) REFERENCES datasource(id) ON DELETE CASCADE
) ENGINE=InnoDB;
```

### agent_datasource_tables
```sql
CREATE TABLE agent_datasource_tables (
    id INT AUTO_INCREMENT PRIMARY KEY,
    agent_datasource_id INT NOT NULL,
    table_name VARCHAR(255) NOT NULL,
    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (agent_datasource_id, table_name),
    FOREIGN KEY (agent_datasource_id) REFERENCES agent_datasource(id)
        ON UPDATE CASCADE ON DELETE CASCADE
) ENGINE=InnoDB;
```

### business_knowledge
```sql
CREATE TABLE business_knowledge (
    id INT NOT NULL AUTO_INCREMENT,
    business_term VARCHAR(255) NOT NULL,           -- 业务名词
    description TEXT,                               -- 描述
    synonyms TEXT,                                  -- 同义词，逗号分隔
    is_recall INT DEFAULT 1,                       -- 是否召回
    agent_id INT NOT NULL,
    created_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    embedding_status VARCHAR(20) DEFAULT NULL,     -- PENDING|PROCESSING|COMPLETED|FAILED
    error_msg VARCHAR(255),
    is_deleted INT DEFAULT 0,
    PRIMARY KEY (id),
    FOREIGN KEY (agent_id) REFERENCES agent(id) ON DELETE CASCADE
) ENGINE=InnoDB;
```

### agent_knowledge
```sql
CREATE TABLE agent_knowledge (
    id INT NOT NULL AUTO_INCREMENT,
    agent_id INT NOT NULL,
    title VARCHAR(255) NOT NULL,
    type VARCHAR(50) NOT NULL,                     -- DOCUMENT | QA | FAQ
    question TEXT,
    content MEDIUMTEXT,
    is_recall INT DEFAULT 1,
    embedding_status VARCHAR(20) DEFAULT NULL,
    error_msg VARCHAR(255),
    source_filename VARCHAR(500),
    file_path VARCHAR(500),
    file_size BIGINT,
    file_type VARCHAR(255),
    splitter_type VARCHAR(50) DEFAULT 'token',
    created_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    is_deleted INT DEFAULT 0,
    is_resource_cleaned INT DEFAULT 0,
    PRIMARY KEY (id)
) ENGINE=InnoDB;
```

### semantic_model
```sql
CREATE TABLE semantic_model (
    id INT NOT NULL AUTO_INCREMENT,
    agent_id INT NOT NULL,                         -- FK → agent
    datasource_id INT NOT NULL,                    -- FK → datasource
    table_name VARCHAR(255) NOT NULL,
    column_name VARCHAR(255) NOT NULL DEFAULT '',  -- 物理字段名
    business_name VARCHAR(255) NOT NULL DEFAULT '',-- 业务名/别名
    synonyms TEXT,                                  -- 同义词
    business_description TEXT,                      -- 给 LLM 的业务描述
    column_comment VARCHAR(255),                    -- 物理注释
    data_type VARCHAR(255) NOT NULL DEFAULT '',
    status TINYINT NOT NULL DEFAULT 1,             -- 0 停用 1 启用
    created_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    FOREIGN KEY (agent_id) REFERENCES agent(id) ON DELETE CASCADE
) ENGINE=InnoDB;
```

### agent_preset_question
```sql
CREATE TABLE agent_preset_question (
    id INT NOT NULL AUTO_INCREMENT,
    agent_id INT NOT NULL,
    question TEXT NOT NULL,
    sort_order INT DEFAULT 0,
    is_active TINYINT DEFAULT 0,
    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    FOREIGN KEY (agent_id) REFERENCES agent(id) ON DELETE CASCADE
) ENGINE=InnoDB;
```

### chat_session
```sql
CREATE TABLE chat_session (
    id VARCHAR(36) NOT NULL,                       -- UUID
    agent_id INT NOT NULL,
    title VARCHAR(255) DEFAULT '新对话',
    status VARCHAR(50) DEFAULT 'active',           -- active | archived | deleted
    is_pinned TINYINT DEFAULT 0,
    user_id BIGINT,
    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    FOREIGN KEY (agent_id) REFERENCES agent(id) ON DELETE CASCADE
) ENGINE=InnoDB;
```

### chat_message (→ chat_session)
```sql
CREATE TABLE chat_message (
    id BIGINT NOT NULL AUTO_INCREMENT,
    session_id VARCHAR(36) NOT NULL,               -- FK → chat_session
    role VARCHAR(20) NOT NULL,                     -- user | assistant | system
    content TEXT NOT NULL,
    message_type VARCHAR(50) DEFAULT 'text',       -- text | sql | result | error
    metadata JSON,
    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    FOREIGN KEY (session_id) REFERENCES chat_session(id) ON DELETE CASCADE
) ENGINE=InnoDB;
```

### user_prompt_config (→ agent, nullable)
```sql
CREATE TABLE user_prompt_config (
    id VARCHAR(36) NOT NULL,                       -- UUID
    name VARCHAR(255) NOT NULL,
    prompt_type VARCHAR(100) NOT NULL,             -- report-generator|planner|sql-generator|python-generator|rewrite
    agent_id INT,                                  -- NULL = 全局配置
    system_prompt TEXT NOT NULL,
    enabled TINYINT DEFAULT 1,
    description TEXT,
    priority INT DEFAULT 0,                        -- 越大越优先
    display_order INT DEFAULT 0,                   -- 越小越靠前
    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    creator VARCHAR(255),
    PRIMARY KEY (id),
    INDEX idx_prompt_type_enabled_priority (prompt_type, agent_id, enabled, priority DESC)
) ENGINE=InnoDB;
```

### logical_relation (→ datasource)
```sql
CREATE TABLE logical_relation (
    id INT NOT NULL AUTO_INCREMENT,
    datasource_id INT NOT NULL,
    source_table_name VARCHAR(100) NOT NULL,       -- 主表
    source_column_name VARCHAR(100) NOT NULL,      -- 主表字段
    target_table_name VARCHAR(100) NOT NULL,       -- 关联表
    target_column_name VARCHAR(100) NOT NULL,      -- 关联表字段
    relation_type VARCHAR(20) DEFAULT NULL,        -- 1:1 | 1:N | N:1
    description VARCHAR(500),                       -- 给 LLM 的业务描述
    is_deleted TINYINT DEFAULT 0,
    created_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    FOREIGN KEY (datasource_id) REFERENCES datasource(id) ON DELETE CASCADE
) ENGINE=InnoDB;
```

### model_config (独立)
```sql
CREATE TABLE model_config (
    id INT NOT NULL AUTO_INCREMENT,
    provider VARCHAR(255) NOT NULL,
    base_url VARCHAR(255) NOT NULL,
    api_key VARCHAR(255) NOT NULL,
    model_name VARCHAR(255) NOT NULL,
    temperature DECIMAL(10,2) DEFAULT 0.00,
    is_active TINYINT DEFAULT 0,
    max_tokens INT DEFAULT 2000,
    model_type VARCHAR(20) NOT NULL DEFAULT 'CHAT',  -- CHAT | EMBEDDING
    completions_path VARCHAR(255),
    embeddings_path VARCHAR(255),
    created_time DATETIME DEFAULT NULL,
    updated_time DATETIME DEFAULT NULL,
    is_deleted INT DEFAULT 0,
    proxy_enabled TINYINT DEFAULT 0,
    proxy_host VARCHAR(255),
    proxy_port INT,
    proxy_username VARCHAR(255),
    proxy_password VARCHAR(255),
    PRIMARY KEY (id)
) ENGINE=InnoDB;
```

---

## 级联删除链

```
删除 agent
  └── CASCADE → agent_datasource
  │     └── CASCADE → agent_datasource_tables
  ├── CASCADE → business_knowledge
  ├── CASCADE → agent_knowledge
  ├── CASCADE → semantic_model
  ├── CASCADE → agent_preset_question
  ├── CASCADE → chat_session
  │     └── CASCADE → chat_message
  └── (user_prompt_config: agent_id 设为 NULL 或手动处理)

删除 datasource
  ├── CASCADE → agent_datasource
  │     └── CASCADE → agent_datasource_tables
  └── CASCADE → logical_relation

删除 chat_session
  └── CASCADE → chat_message
```

---

## 与 Python 版对照

| Java 表名 | Python 表名 | 状态 |
|-----------|------------|------|
| agent | agent | 已实现 |
| datasource | datasource | 已实现 |
| agent_datasource | agent_datasource | 已实现 |
| agent_datasource_tables | agent_datasource_tables | 已实现 |
| business_knowledge | knowledge | 已实现 (合并了部分 agent_knowledge 字段) |
| agent_knowledge | — | Python 版合并到 knowledge 表 |
| semantic_model | semantic_model | 已实现 |
| agent_preset_question | agent_preset_question | 已实现 |
| chat_session | chat_session | 已实现 |
| chat_message | chat_message | 已实现 |
| user_prompt_config | prompt_config | 已实现 |
| model_config | model_config | 已实现 |
| logical_relation | logical_relation | 已实现 |
| — | human_feedback | Python 扩展 |
| — | query_plan | Python 扩展 |
