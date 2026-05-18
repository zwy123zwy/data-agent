# CHANGELOG

## 2026-05-18

- **前端交互模式设计文档**: 新增 `docs/superpowers/specs/2026-05-18-frontend-interaction-design.md`。确定 B 方案（两栏+可展开抽屉）、思考气泡单例刷新、执行面板手动关闭、节点三种交互（展开 tool / 定位气泡 / Popover 详情）、Zustand executionStore 状态结构和 SSE→UI 完整映射表。经 4 轮审计修复（15 个问题），前后端协议字段统一对齐 `NODE_NAME_MAP`。
- **前端交互模式全栈实施文档**: 新增 `docs/superpowers/plans/2026-05-18-frontend-interaction-implementation.md`。1746 行全栈技术文档，含前端 8 个 Task（executionStore、ThinkingBubble、ExecutionDrawer、AgentRound、ToolItem 组件 + streamRequest.ts/AgentRun.tsx 改造）+ 后端 3 个 Task（SSEPayload 协议升级、Controller 透传、17 节点 format_sse 声明 agentName/toolName）+ 集成验证 4 场景。前后端接口契约完整对齐。
- **闲聊回复节点 (chitchat_node)**: 意图识别为非数据分析时，不再静默 END，改为通过 `chitchat_node` 调用 LLM 生成友好的中文对话回复。`graph.py` 路由 `route_after_intent` 新增 `chitchat_node` 分支。`streaming_graph_controller.py` 注册 `NODE_NAME_MAP` 和 `USER_VISIBLE_NODES`。
- **清理死文件和过时引用**: 删除 `app/services/hybrid_search.py`（无调用方）、`milvus-docker-compose.yml`（使用 Chroma 而非 Milvus），清理所有 `__pycache__/` 目录和 `checkpoints.db` 运行时文件，更新 `config.py` 和 `services/__init__.py` 中的过时引用。

## 2026-05-17

- **意图识别置信度 + 人工确认闭环**: `intent_recognition.py` 新增 confidence 字段（LLM 自评 0.0-1.0），置信度 < 0.7 时通过 `interrupt()` 暂停等人工确认，用户反馈喂回 LLM 重判（最多 1 次）。`streaming_graph_controller.py` 接入 `MultiTurnContextManager`（请求前读历史上下文，完成后记录本轮对话），interrupt 处理器支持 `intent_confirm` 类型检测。`state.py` 新增 4 个 state key。
- **日志终端可见修复**: `streaming_graph_controller.py` 添加 StreamHandler 到模块 logger，确保 uvicorn worker 子进程中 `logger.info()` 输出到终端。

## 2026-05-16

- **WorkflowNode 基类 + 16 节点重构**: 创建 `app/workflows/node_base.py` — SSEPayload dataclass + WorkflowNode ABC（自声明 requires/provides/applicable_data_sources，自动 Langfuse 埋点 + sse_output 注入）。16 个 LangGraph 节点全部从独立 async 函数改为 WorkflowNode 子类，每个节点实现 `execute()` + `format_sse()`。Controller 的 260 行 if/elif 分发链替换为 50 行通用 sse_output 读取逻辑。移除 `_NODE_MSG` 冗余映射（每个节点的 format_sse 自描述输出）。移除 `app/workflows/node_messages.py`。graph.py 无需修改（节点实例保持 callable）。
- **项目清理**: 删除 `restart_server.bat`（端口已过时）、`checkpoints.db-wal/shm`（SQLite 运行时文件）。清理 9 个 `__pycache__` 目录（121 个 .pyc 文件）。识别 2 个死服务（`hybrid_search.py`、`multi_turn.py` 未接入）。
- **项目全面检查**: 16 节点注册对齐、Model/Schema 匹配、gitignore 覆盖验证。测试：174 passed。
- **统一 API 响应格式 — ApiResponse 类（对齐 Java）**: 创建 `app/schemas/common.py` 的 `ApiResponse` 类（对齐 Java `ApiResponse<T>`），提供 `ok(data, message)` / `fail(message, data)` 工厂方法。批量更新 11 个 controller（semantic_model、business_knowledge、model_config、chat、agent、agent_knowledge、datasource、agent_datasource、agent_preset_question、feedback、schema_controller），移除所有手动构造 `{"success": True, ...}` dict 的代码，去除 datasource_controller 的 `response_model` 声明。修复 ChatSessionSidebar 创建/删除按钮无响应的问题（后端裸返数据导致前端 `res.data.data` 为 undefined）。
- **Controller 重构**: 8 个 controller 文件中手动构造的 `{"success": True/False, ...}` dict 全部替换为 `ApiResponse.ok()` / `ApiResponse.fail()` 调用，统一响应构建方式。保留含额外根级别字段（`total`, `pageNum`, `hasCustomConfig` 等）的返回不变。

## 2026-05-15

- **添加 Workflow 架构文档**: `docs/WORKFLOW_ARCHITECTURE.md` — 16 节点拓扑图、每个节点的 I/O 数据、State Key 生产消费关系映射、数据流依赖链、Java 节点对应表。
- **LLM 热切换重构 — 对齐 Java 清缓存+懒重建模式**: `llm_service` 新增 `invalidate()` + `_ensure_configured()` + `set_session_factory()`，activate 端点调用 `invalidate()` 即时标记失效，下一个 `chat()` 按需查 DB 重建客户端。去掉每个请求的 `resolve_and_configure_llm()`。涉及 `llm.py`、`model_config_controller.py`、`streaming_graph_controller.py`、`graph_controller.py`、`mcp_server.py`、`main.py`。
- **默认启用热重载**: `main.py` 改为 `--no-reload` 关闭（而非 `--reload` 开启），`python main.py` 直接启动即带 WatchFiles 自动重载。

## 2026-05-14

- **数据库表结构对齐 Java 版本 (13 张表)**: 重命名 `datasource.database` → `database_name`，修复默认值/约束/索引共 40+ 处变更，新增 UNIQUE 约束 2 个，新增索引 34 个。
- **database → database_name 级联修改**: 更新 `schemas/datasource.py`、`datasource_handler.py`、`datasource_service.py`、`schema_service.py`、`schema_recall.py`、`sql_execute.py`、`table_relation.py`、`seed_datasources.py`、`create_tables.sql`。
- **添加文档**: `docs/DB_SCHEMA_ALIGNMENT_FIX.md`（修复记录）、`docs/Java_DB_Schema_Reference.md`（Schema 对照参考）、`CLAUDE.md`（项目指南）。
- **添加持久记忆**: 每次修改后追加 CHANGELOG.md。
