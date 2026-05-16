# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Python Agent V2 — a progressive reproduction of the Java DataAgent using FastAPI + LangGraph. It implements Text-to-SQL + Python analysis + intelligent reporting via an LLM-powered workflow.

**Port**: 8100 (dev), API docs at `http://localhost:8100/docs`

## Commands

```bash
# Install
pip install -r requirements.txt

# Initialize database (reads .env for DATABASE_URL)
python scripts/init_db.py

# Start server (hot reload)
python main.py --reload

# Or directly via uvicorn
uvicorn app.main:app --reload --port 8100

# Run tests
pytest tests/ -v

# Run a single test
pytest tests/test_integration_stream.py -v

# Format + lint
black app/ tests/ --line-length 100
ruff check app/ tests/
```

## Configuration

All config flows through `app/core/config.py` → `Settings` (Pydantic BaseSettings), loaded from `.env`. Key settings:

| Setting | Purpose |
|---------|---------|
| `DATABASE_URL` | MySQL (async `aiomysql`) or SQLite (`aiosqlite`) |
| `OPENAI_API_KEY/BASE/MODEL` | LLM provider (OpenAI-compatible) |
| `EMBEDDING_*` | Separate embedding model (default: Ollama bge-m3) |
| `CHROMA_HOST/PORT` | Chroma vector DB (Docker) |
| `checkpointer_type` | `"sqlite"` (persistent, default) or `"memory"` |
| `CODE_EXECUTOR_EXECUTOR_TYPE` | `local` / `docker` / `ai-sim` |

## Architecture

### Request Flow

```
HTTP → FastAPI app (app/main.py)
  → middleware (CORS → ApiResponseMiddleware)
  → 18 controllers (app/api/*.py)
    → Services (app/services/*.py) → ORM Models (SQLAlchemy)
    → OR: Workflow (LangGraph StateGraph) → SSE streaming
```

### LangGraph Workflow Topology (16 nodes, 3 phases)

**Phase 1 — Frontend Processing** (linear):
```
START → intent_recognition → (chitchat→END)
  → knowledge_recall → query_rewrite → schema_recall → table_relation (with retry loop)
  → feasibility → planner
```

**Phase 2 — PlanExecutor Dispatch Loop** (the core):
```
plan_executor → dispatches based on step type:
  → sql_generate → semantic_consistency → sql_execute → (back to plan_executor)
  → python_generate → python_execute → python_analyze → (back to plan_executor)
  → human_feedback → (approve→plan_executor / reject→planner)
  → report_generator → END
```

**Phase 3 — Report**: `report_generator` produces HTML/Markdown with ECharts.

The workflow is defined in `app/workflows/graph.py`. All state keys are defined as `StateKeys` constants in `app/workflows/state.py` to eliminate magic strings.

### SSE Streaming Protocol

The main API endpoint is `GET /api/stream/search` (aligns with the Java frontend). It uses `astream(stream_mode="updates")` — each node completion yields a `GraphNodeResponse` JSON over SSE:

- `data: {agentId, threadId, nodeName, textType, text, error, complete}` — node output
- `event: complete` / `event: error` / `event: paused` — lifecycle events

Node names are mapped from Python snake_case to Java CamelCase via `NODE_NAME_MAP` in `streaming_graph_controller.py`.

### Human Feedback (HITL)

When `human_feedback=true`, the workflow pauses at the `human_feedback` node via LangGraph's `interrupt()`. Resume by re-calling the same endpoint with `threadId` + `humanFeedbackContent`. The checkpointer (`AsyncSqliteSaver` by default) persists state across restarts.

### LLM Layer

- `app/core/llm.py:llm_service` — global singleton, all AI calls go through `chat()` or `chat_stream()`
- `app/core/model_registry.py:ModelRegistry` — dynamic hot-swapping of LLM models at runtime (no restart needed)

### Code Execution

`app/core/code_executor.py` (`ExecutorFactory`): `local` (subprocess), `docker` (sandboxed), `ai-sim` (LLM-simulated).

### Key Services

- `hybrid_search.py` — Vector + keyword hybrid retrieval (Chroma)
- `multi_turn.py` — Conversation context management
- `mcp_server.py` — MCP protocol server for Claude Desktop
- `langfuse_service.py` — Observability tracing

## Java Alignment

This project mirrors the Java DataAgent's architecture. Key mappings:

| Python | Java |
|--------|------|
| `app/workflows/graph.py` | `DataAgentConfiguration.nl2sqlGraph()` |
| `app/workflows/state.py` | `OverAllState.java` + `Constant.java` |
| `streaming_graph_controller.py` | `GraphController.java` + `GraphServiceImpl.java` |
| `app/core/llm.py:llm_service` | `LlmService.java` |
| `app/core/model_registry.py` | `AiModelRegistry.java` |
| `app/core/code_executor.py` | `CodePoolExecutorService.java` |
| `route_after_*` functions | `Dispatcher` pattern |

The Python project uses snake_case for node names internally but maps to Java PascalCase node names for the frontend via `NODE_NAME_MAP`.

## Claude Code Development Rules

Claude Code 在本仓库中编写或修改代码时，必须先理解现有架构边界，再进行最小必要变更。所有实现应服务于 DataAgent 的可维护性、可观测性和面试演示闭环。

### Three-Level Architecture Discipline

任何新增功能或较大改造，都按三级职责拆分和评审：

1. **Architecture Level**
   - 先判断变更属于 API、Service、Workflow、LLM、Executor、Persistence、Observability 中的哪一层。
   - 不跨层直接调用：Controller 不直接操作数据库，Workflow 节点不绕过已有 Service，Service 不直接拼接 SSE 协议。
   - 保持与 Java DataAgent 的概念映射一致；如果 Python 命名与 Java 前端协议不同，必须通过显式映射层适配。
   - 涉及状态流转时，优先更新 `app/workflows/state.py` 的 `StateKeys`，避免魔法字符串。

2. **Harness Level**
   - 为可运行、可验证、可演示的闭环设计代码，而不是只完成局部函数。
   - 新增节点、服务或接口时，应同步考虑输入、输出、异常、日志、指标、测试样例和演示路径。
   - 需要接入外部资源时，通过 `app/core/config.py` 的 `Settings` 注入配置，不在业务代码中硬编码密钥、URL、模型名或端口。
   - 对 LLM、数据库、向量库、代码执行器等不稳定依赖，应保留降级、错误上报或可替换边界。

3. **Engineer Level**
   - 代码实现保持小步、清晰、可测试；优先复用现有模块、类型和工具函数。
   - 函数只承担一个清晰职责；复杂流程拆成私有 helper 或独立 Service，不把流程逻辑堆在 Controller 中。
   - 异步代码保持 async/await 链路一致，不在事件循环中执行阻塞 I/O。
   - 数据结构优先使用 Pydantic Model、TypedDict、dataclass 或明确的类型注解，不用松散 dict 传递核心业务对象。
   - 错误处理要保留上下文，日志中说明失败阶段、关键 id、节点名或 step 类型，但不得打印密钥和敏感数据。

### Commenting Rules

- 必须为复杂业务流程、LangGraph 路由条件、重试/降级策略、协议兼容逻辑添加必要注释。
- 注释解释“为什么这样做”和“边界条件是什么”，不要重复代码表面含义。
- 公共函数、Workflow 节点、跨模块 Service 方法应有简短 docstring，说明输入、输出和副作用。
- 临时兼容逻辑必须注明原因和后续删除条件；不要留下无上下文的 TODO。
- 不为简单赋值、明显变量名或直观分支添加噪音注释。

### Workflow And State Rules

- 新增 LangGraph 节点时，同时检查 `graph.py`、`state.py`、路由函数、SSE 输出和 Java 节点名映射。
- 节点输出必须写入明确的 state key，不允许隐式依赖上游节点的临时局部变量。
- PlanExecutor 调度相关变更必须保持 SQL、Python、Human Feedback、Report 四类步骤的回环语义清晰。
- Human-in-the-loop 变更必须验证 threadId、checkpoint 和 resume 行为。

### API And Protocol Rules

- API 返回结构优先使用已有响应模型和中间件，不新增不兼容字段，除非同步更新文档。
- SSE 协议变更必须兼容现有 Java 前端期望的 `agentId`、`threadId`、`nodeName`、`textType`、`text`、`error`、`complete` 字段。
- Controller 只负责参数解析、权限/校验、调用编排和协议输出；业务判断放到 Service 或 Workflow。
- **禁止在 Controller 中硬编码 UI 文案、Prompt 模板、SSE 进度消息**。所有面向用户的文本和提示词必须收敛到 `_NODE_MSG` 映射、Prompt 配置文件（DB `prompt_config` 表）或独立的 constants 模块中。Controller 只通过 key 引用文案，不做内联拼接中文/英文字符串。

### Testing And Verification Rules

- 修复 bug 必须优先补充或更新能复现问题的测试。
- 新增 Workflow、SQL、Python 执行、SSE、配置相关逻辑时，至少覆盖成功路径和一个关键失败路径。
- 提交前根据变更范围运行最小必要验证：单测、集成测试、lint、或手动 API/SSE 验证。
- 如果某项验证无法运行，必须在交付说明中明确原因和剩余风险。

### Documentation Rules

- 架构、协议、配置、演示路径发生变化时，同步更新 `docs/` 下对应文档。
- 面试演示相关改动需要保持“问题 -> 处理链路 -> 结果 -> 可观测证据”的讲解闭环。
- 文档应说明真实约束和边界，不写无法从代码或测试证明的承诺。

### Git Commit And Push Rules

- 每次代码修改完成后，必须提交到本地仓库（`git add` + `git commit`），不等待多次修改堆积。
- 累计 10 次本地提交后，一次性 `git push` 到远程。
- 每次提交后更新 `CHANGELOG.md` 记录变更内容。
- 提交 message 遵循简洁原则：说明"做了什么"和"为什么"。
