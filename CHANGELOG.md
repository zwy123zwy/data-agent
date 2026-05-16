# CHANGELOG

## 2026-05-16

- **项目清理**: 删除 `restart_server.bat`（端口已过时）、`checkpoints.db-wal/shm`（SQLite 运行时文件）。清理 9 个 `__pycache__` 目录（121 个 .pyc 文件）。识别 2 个死服务（`hybrid_search.py`、`multi_turn.py` 未接入）。
- **项目全面检查**: 16 节点注册对齐、Model/Schema 匹配、gitignore 覆盖验证。测试：174 passed。

## 2026-05-15

- **添加 Workflow 架构文档**: `docs/WORKFLOW_ARCHITECTURE.md` — 16 节点拓扑图、每个节点的 I/O 数据、State Key 生产消费关系映射、数据流依赖链、Java 节点对应表。
- **LLM 热切换重构 — 对齐 Java 清缓存+懒重建模式**: `llm_service` 新增 `invalidate()` + `_ensure_configured()` + `set_session_factory()`，activate 端点调用 `invalidate()` 即时标记失效，下一个 `chat()` 按需查 DB 重建客户端。去掉每个请求的 `resolve_and_configure_llm()`。涉及 `llm.py`、`model_config_controller.py`、`streaming_graph_controller.py`、`graph_controller.py`、`mcp_server.py`、`main.py`。
- **默认启用热重载**: `main.py` 改为 `--no-reload` 关闭（而非 `--reload` 开启），`python main.py` 直接启动即带 WatchFiles 自动重载。

## 2026-05-14

- **数据库表结构对齐 Java 版本 (13 张表)**: 重命名 `datasource.database` → `database_name`，修复默认值/约束/索引共 40+ 处变更，新增 UNIQUE 约束 2 个，新增索引 34 个。
- **database → database_name 级联修改**: 更新 `schemas/datasource.py`、`datasource_handler.py`、`datasource_service.py`、`schema_service.py`、`schema_recall.py`、`sql_execute.py`、`table_relation.py`、`seed_datasources.py`、`create_tables.sql`。
- **添加文档**: `docs/DB_SCHEMA_ALIGNMENT_FIX.md`（修复记录）、`docs/Java_DB_Schema_Reference.md`（Schema 对照参考）、`CLAUDE.md`（项目指南）。
- **添加持久记忆**: 每次修改后追加 CHANGELOG.md。
