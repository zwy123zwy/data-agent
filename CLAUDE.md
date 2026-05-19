# CLAUDE.md

## What Is This

**Data Agent Backend** — FastAPI + LangGraph data analysis agent backend, modeled after ByteDance Volcengine DataAgent 3.0.

- Port: 8200, Docs: `http://localhost:8200/docs`
- Frontend: `../data-agent-frontend` (Vue3 + Vite, port 5173)
- Dual runtime: `?runtime=v1` (legacy 17-node pipeline) / `?runtime=v2` (new Agent Runtime, in development)

---

## Quick Start

```bash
pip install -r requirements.txt
python scripts/init_db.py        # init database
python main.py --reload          # start server (hot reload)
pytest tests/ -v                 # run tests
black app/ tests/ --line-length 100 && ruff check app/ tests/  # lint
```

---

## Directory Map

```
app/
├── api/          → 18 Controllers (HTTP entry), key: streaming_graph_controller.py
├── services/     → 20 Services (business logic), key: agent_service / datasource_service
├── workflows/    → LangGraph v1 legacy (graph.py + state.py + nodes/17 nodes)
├── models/       → 17 SQLAlchemy ORM tables
├── schemas/      → Pydantic request/response models
└── core/         → Infrastructure (config / database / llm / code_executor / vector_store)

agent_runtime/    → V2 new runtime (in development, not yet created)
```

**Key files**:
- `streaming_graph_controller.py` — SSE streaming API, runtime routing entry point
- `workflows/graph.py` — LangGraph graph definition (v1)
- `workflows/state.py` — WorkflowState + StateKeys constants (no magic strings)
- `core/config.py` — Settings hub, config source for all modules
- `core/llm.py` — Global LLM singleton `llm_service`

---

## Config (.env)

| Key | Purpose |
|-----|---------|
| `DATABASE_URL` | MySQL / SQLite |
| `OPENAI_API_KEY/BASE/MODEL` | LLM provider |
| `EMBEDDING_*` | Embedding model (default: Ollama bge-m3) |
| `CHROMA_HOST/PORT` | Vector database |
| `checkpointer_type` | sqlite (default) / memory |
| `CODE_EXECUTOR_EXECUTOR_TYPE` | local / docker / ai-sim |

---

## V1 Legacy Topology (runtime=v1, stable, keep compatible)

```
START → intent_recognition → (chitchat→END)
  → knowledge_recall → query_rewrite → schema_recall → table_relation
  → feasibility → planner
  → plan_executor →┬→ sql_generate → semantic_consistency → sql_execute ──┐
                   ├→ python_generate → python_execute → python_analyze ──┤
                   ├→ human_feedback → (approve/reject)                   │
                   └← ─────────────────────────────────────────────────── ┘
  → report_generator → END
```

## V2 New Architecture (runtime=v2, in development)

```
Gateway (intent classification + confidence routing)
  conf≥0.7 → execute directly
  0.3-0.7  → ask clarification
  <0.3     → fallback to v1

→ ContextEngine (assemble RuntimeContext from DB)
→ Orchestrator (Plan+React loop)
  → Explorer Agent (NL2SQL + 3-parallel SQL + majority voting)
  → Insight Agent (Python analysis, skippable for simple results)
  → Report Agent (collect Artifacts → generate report)
```

**3-way SQL voting**: 3/3 agree→conf=1.0, 2/3→conf=0.8, 0/3→conf=0.4 triggers rewrite

---

## SSE Protocol

Endpoint: `GET /api/stream/search`

Legacy fields (both v1/v2): `agentId / threadId / nodeName / textType / text / error / complete`

New fields (v2 only): `runId / eventType / agentName / action / status / summary / artifactRefs`

Frontend logic: `if (eventType) → V2 path, else → NODE_TO_EXECUTION mapping`

---

## Dev Rules

### Layer boundaries (no cross-layer calls)
- v1: Controller → Service → Workflow node
- v2: Controller → Gateway → Orchestrator → Agent → Tool

### When writing code
- All new code must have Chinese inline comments
- Legacy code comment format: `# LEGACY: runtime=v1 — keep for compatibility, do not delete`
- Tools return `ToolResult`, not `GraphNodeResponse`
- Prefer Pydantic Model > TypedDict > loose dict

### After writing code
- `git add + git commit` after every change, `git push` after every 10 commits
- Update `CHANGELOG.md` after each commit
- Cover at least: success path + one critical failure path

### Forbidden
- Hardcoding UI text / Prompt templates / progress messages in Controller
- Cross-layer direct calls (e.g. Controller directly touching DB)
- Magic strings (use StateKeys constants)
