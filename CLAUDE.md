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
