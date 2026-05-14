# 数据库表结构对齐修复记录

> 目标: 将 Python Agent V2 的 13 张表完全对齐 Java DataAgent schema
> 参考: `docs/Java_DB_Schema_Reference.md`
> 日期: 2026-05-14

---

## 修复清单

### P0 — 严重问题（列名/默认值/约束不兼容）

| # | 表 | 问题 | 修复 |
|---|-----|------|------|
| 1 | `datasource` | 列名 `database` 应为 `database_name` | 重命名列 |
| 2 | `datasource` | `status` 默认 `"active"` 应为 `"inactive"` | 修改默认值 |
| 3 | `datasource` | `test_status` 默认 `"untested"` 应为 `"unknown"` | 修改默认值 |
| 4 | `datasource` | `host`/`port`/`username`/`password` 为 Optional 应为 NOT NULL | 添加 NOT NULL |
| 5 | `agent_datasource` | `is_active` 默认 `1` 应为 `0` | 修改默认值 |
| 6 | `agent_datasource` | 缺少 UNIQUE(agent_id, datasource_id) | 添加 UniqueConstraint |
| 7 | `agent_datasource_tables` | 缺少 UNIQUE(agent_datasource_id, table_name) | 添加 UniqueConstraint |

### P1 — 索引缺失

| # | 表 | 缺失索引 | 状态 |
|---|-----|---------|------|
| 8 | `datasource` | idx_name, idx_type, idx_status, idx_creator_id | ✅ |
| 9 | `agent_datasource` | idx_agent_id, idx_datasource_id, idx_is_active | ✅ |
| 10 | `agent` | idx_name, idx_status, idx_category, idx_admin_id | ✅ |
| 11 | `business_knowledge` | idx_business_term, idx_is_recall, idx_embedding_status, idx_is_deleted | ✅ |
| 12 | `logical_relation` | idx_datasource_id, idx_source_table(composite) | ✅ |
| 13 | `agent_preset_question` | idx_agent_id, idx_sort_order, idx_is_active | ✅ |
| 14 | `chat_session` | idx_agent_id, idx_user_id, idx_status, idx_is_pinned, idx_create_time | ✅ |
| 15 | `chat_message` | idx_session_id, idx_role, idx_message_type, idx_create_time | ✅ |
| 16 | `user_prompt_config` | idx_enabled, idx_create_time, idx_prompt_type_enabled_priority(复合), idx_display_order | ✅ |
| 17 | `semantic_model` | idx_field_name, idx_status | ✅ |

### P2 — 类型/约束微调

| # | 表 | 问题 | 修复 |
|---|-----|------|------|
| 18 | `datasource` | `name` String(100)→String(255), `type` String(20)→String(50) | ✅ |
| 19 | `agent` | `name` String(100)→String(255) | ✅ |
| 20 | `business_knowledge` | 缺少 FK agent_id→agent(id) CASCADE | ✅ |
| 21 | `logical_relation` | `description` Text→String(500) | ✅ |
| 22 | `user_prompt_config` | `system_prompt` Optional→NOT NULL, `name` 200→255, `prompt_type` 50→100 | ✅ |
| 23 | `semantic_model` | `column_name` nullable→NOT NULL DEFAULT '' | ✅ |
| 24 | `agent_knowledge` | `error_msg` Text→String(255) | ✅ |

### 未修改（Python 扩展，保留）

- `agent.human_review_enabled` — Python 扩展字段（Java 通过请求参数控制）
- `semantic_model.sample_values` / `semantic_model.metadata_` — Python 扩展
- `knowledge.embedding_id` / `knowledge.metadata_` / `knowledge.enabled` — Python 扩展

---

## 影响的非 Model 文件

`database` → `database_name` 重命名影响以下文件：

| 文件 | 修改行数 | 状态 |
|------|---------|------|
| `app/schemas/datasource.py` | 3 处 | ✅ |
| `app/core/datasource_handler.py` | ~12 处 | ✅ |
| `app/services/datasource_service.py` | 1 处 | ✅ |
| `app/services/schema_service.py` | 5 处 | ✅ |
| `app/workflows/nodes/schema_recall.py` | 1 处 | ✅ |
| `app/workflows/nodes/sql_execute.py` | 3 处 | ✅ |
| `app/workflows/nodes/table_relation.py` | 1 处 | ✅ |

---

## SQL 迁移执行记录

> 执行时间: 2026-05-14 22:04 CST
> 数据库: mysql+aiomysql://root@localhost:3306/dataagent

### 列操作

```sql
-- ✅ 成功
ALTER TABLE datasource CHANGE COLUMN `database` `database_name` VARCHAR(255) NOT NULL;
ALTER TABLE datasource MODIFY COLUMN `status` VARCHAR(50) NOT NULL DEFAULT 'inactive';
ALTER TABLE datasource MODIFY COLUMN `test_status` VARCHAR(50) NOT NULL DEFAULT 'unknown';
```

### 约束操作

```sql
-- ℹ️ 已存在，跳过
ALTER TABLE agent_datasource ADD UNIQUE KEY `uk_agent_datasource` (`agent_id`, `datasource_id`);
-- ✅ 成功
ALTER TABLE agent_datasource_tables ADD UNIQUE KEY `uk_agent_ds_table` (`agent_datasource_id`, `table_name`);
```

### 索引操作

**新增 34 个，跳过 4 个（已存在）**

| 表 | 新增索引 |
|---|---------|
| `datasource` | idx_name, idx_type, idx_status, idx_creator_id |
| `agent` | idx_name, idx_status, idx_category, idx_admin_id |
| `agent_datasource` | idx_agent_id, idx_datasource_id, idx_is_active |
| `business_knowledge` | idx_business_term, idx_is_recall, idx_embedding_status, idx_is_deleted |
| `logical_relation` | idx_datasource_id, idx_source_table |
| `agent_preset_question` | idx_agent_id, idx_sort_order, idx_is_active |
| `chat_session` | idx_agent_id, idx_user_id, idx_status, idx_is_pinned, idx_create_time |
| `chat_message` | idx_session_id, idx_role, idx_message_type, idx_create_time |
| `user_prompt_config` | idx_enabled, idx_create_time, idx_prompt_type_enabled_priority, idx_display_order |
| `semantic_model` | idx_field_name, idx_status |
| `agent_knowledge` | idx_agent_id_status, idx_embedding_status, idx_is_deleted |

跳过 4 个: uk_agent_datasource (已存在), agent_datasource.idx_agent_id, agent_datasource.idx_datasource_id, business_knowledge.idx_agent_id
