# CLAUDE.md

## What This Is

**Data Agent Backend** — FastAPI + LangGraph data analysis agent backend, modeled after ByteDance Volcengine DataAgent 3.0.

- Port: 8200, Docs: `http://localhost:8200/docs`
- Frontend: `../data-agent-fronted` (React 19 + TypeScript + Vite + Ant Design + Zustand, dev port **3000** per `vite.config.ts`)
- Dual runtime: `?runtime=v1` (legacy 17-node pipeline) / `?runtime=v2` (new Agent Runtime, in development)
- **Docs index**: `../docs/README.md` — **design/roadmap archived** `../docs/archive/2026-05-21-design-and-roadmap/`
- **Code comments (required)**: `../docs/CODING-CONVENTIONS.md` — every new/changed business code must include **`[阶段N] 功能说明`** in Chinese (N = OpenSpec Phase 0–5)

---

## Harness Engineering

**Agent = Model + Harness**

Harness is the deterministic runtime infrastructure wrapped around the probabilistic LLM core. Without it, you have a chatbot. With it, you have a production Agent.

Six capabilities every design decision must align to:

| # | Capability | What It Means | In This System |
|---|-----------|---------------|----------------|
| **1** | **Tool Access** | Standardized Agent↔Tool protocol: I/O contracts, sandbox, error propagation | `BaseTool` ABC + `ToolResult` + `ToolRegistry` |
| **2** | **A2A Delegation** | Agent-to-Agent handoff, delegation, coordination | Orchestrator explicitly invokes Explorer → Insight → Reporter subgraphs |
| **3** | **Intelligent Routing** | Route each request by intent, complexity, cost, and latency | Gateway 5-mode split (chitchat/smart_query/deep_research/report/clarification) + v1 fallback |
| **4** | **Memory** | Structured management of working context, episodic experience, long-term knowledge | `ContextEngine` → `RuntimeContext` (datasets, semantic_model, knowledge, conversation history) |
| **5** | **Sandbox & Permissions** | Constrain Agent action scope, prevent overreach | SQL validation + code executor sandbox (local/docker/ai-sim) + HITL human approval |
| **6** | **Observability** | Per-call cost, latency, success rate, failure mode tracing | Langfuse instrumentation + SSE event stream + Artifact provenance chain |

**Three design levels** — Harness cuts through all three:

| Level | Owns | Harness Concern | Rule |
|-------|------|----------------|------|
| **Architecture** | Layer boundaries, concept mapping, coexistence | Observation points + degradation switches at every boundary | No cross-layer direct calls |
| **Harness** | Engineering constraints for the six capabilities | Every module proves: input contract, output validation, circuit breaker, instrumentation, cost cap | Tool → ToolResult, Agent → Observation, Run → Metrics |
| **Engineer** | Code implementation, type safety | Extend Harness base classes, never bypass constraints | async throughout, Pydantic types, small testable steps |

**Litmus test**: if a piece of code cannot answer "which Harness capability does this serve?", the architecture is incomplete.

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
├── workflows/    → V1 legacy (graph.py + state.py + nodes/17 nodes)
├── models/       → 17 SQLAlchemy ORM tables
├── schemas/      → Pydantic request/response models
└── core/         → Infrastructure (config / database / llm / code_executor / vector_store)

agent_runtime/    → V2 runtime (in development, not yet created)
```

**Key files**:
- `streaming_graph_controller.py` — SSE streaming API, runtime routing entry point
- `workflows/graph.py` — V1 LangGraph graph definition
- `workflows/state.py` — `WorkflowState` + `StateKeys` constants (no magic strings)
- `core/config.py` — Settings hub
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

## V1 Topology (runtime=v1, stable, keep compatible)

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

Fixed 17-node LangGraph pipeline. Every request walks the full chain — no intent-based shortcut, no dynamic tool selection. Harness coverage: Sandbox #5 (code executor, SQL validation) + partial Observability #6 (Langfuse via WorkflowNode base class).

---

## V2 Architecture (runtime=v2, in development)

```
Gateway (intent classification + confidence routing)
  conf ≥ 0.7  → execute directly via V2
  0.3 ≤ conf < 0.7 → ask clarification
  conf < 0.3  → fallback to V1

→ ContextEngine (assemble RuntimeContext from DB)
→ Orchestrator (Plan + React loop)
  → Explorer Agent (NL2SQL + 3-parallel SQL + majority voting)
  → Insight Agent (Python analysis, skippable for simple queries)
  → Report Agent (collect Artifacts → generate report)
```

**3-way SQL voting**: 3/3 agree → conf=1.0, 2/3 → conf=0.8, 0/3 → conf=0.4 triggers rewrite.

Full Harness coverage: Tool #1 (12 Tool wrappers, ToolResult contract), A2A #2 (Orchestrator→Agent subgraphs), Routing #3 (Gateway + voting), Memory #4 (ContextEngine), Sandbox #5 (SQL validation + code sandbox + HITL), Observability #6 (Artifact provenance + SSE event stream + metrics).

---

## SSE Protocol

Endpoint: `GET /api/stream/search`

Dual protocol — each SSE frame carries both V1 compatibility and V2 semantics:

- **Legacy fields** (v1+v2): `agentId / threadId / nodeName / textType / text / error / complete`
- **V2 fields** (v2 only): `runId / eventType / agentName / action / status / summary / artifactRefs`

Frontend logic: `if (eventType) → V2 path, else → NODE_TO_EXECUTION mapping`

---

## Dev Rules

### Harness Engineering

1. **Every module declares its Harness capability** — annotate classes and key methods with `# [Harness: Tool #1]` etc.
2. **Tool → ToolResult always** — never return bare dict/str. Unified success/failure/timeout/circuit-breaker semantics.
3. **Agent → Observation always** — every tool invocation produces an Observation (input_summary, output_summary, status, duration_ms).
4. **Run → Metrics always** — every Agent run outputs total tokens, LLM call count, total duration.
5. **A2A for cross-Agent calls** — never import another Agent's internals directly. Always delegate through the Orchestrator.
6. **Model selection via policy name** — never hardcode model names. Reference policies (e.g. `policy/sql_generator`) resolved by Gateway.
7. **Every loop has a circuit breaker** — max_rounds on every loop, timeout on every LLM call, cost cap on every run.

### Layer Boundaries

- v1: Controller → Service → Workflow node
- v2: Controller → Gateway → Orchestrator → Agent → Tool

### When Writing Code

- All new code must have Chinese inline comments
- Harness annotation format: `# [Harness: <capability> #<number>]` on classes and key methods
- Legacy code comment format: `# LEGACY: runtime=v1 — keep for compatibility, do not delete`
- Prefer Pydantic Model > TypedDict > loose dict
- Tools return `ToolResult`, not `GraphNodeResponse`

### After Writing Code

- `git add` + `git commit` after each change
- Update `CHANGELOG.md`
- Cover: success path + one critical failure path + one Harness constraint (circuit breaker / timeout / degradation)

### Forbidden

- Hardcoding UI text, prompt templates, or progress messages in Controller
- Cross-layer direct calls (e.g. Controller touching DB directly)
- Magic strings (use `StateKeys` constants)
- Bypassing Harness to call LLM directly (must go through Tool or Agent subgraph)
- Hardcoding model names (must use Gateway policy routing)
