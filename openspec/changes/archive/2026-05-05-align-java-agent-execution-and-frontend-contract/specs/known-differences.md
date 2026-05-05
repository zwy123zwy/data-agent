# Known Differences: Python vs Java Agent

## Intentional Differences

### 1. Technology Stack
| Aspect | Java | Python |
|--------|------|--------|
| Framework | Spring Boot + Spring AI | FastAPI + LangGraph |
| Workflow Engine | Spring AI StateGraph | LangGraph StateGraph |
| Streaming | Spring Flux\<ServerSentEvent\> | FastAPI StreamingResponse |
| Human-in-Loop | `CompiledGraph.interruptBefore()` | LangGraph `interrupt()` |

### 2. API Path Differences
- Python uses `/api/agents` (plural) for Agent management, Java uses `/api/agent` (singular)
- Python nests Knowledge under Agent: `/api/agents/{id}/knowledge`, Java uses independent `/api/agent-knowledge`
- Python nests SemanticModel under Agent: `/api/agents/{id}/semantic-models`, Java uses independent `/api/semantic-model`

### 3. Streaming Differences
- Java: Token-level streaming via `StreamingOutput` for individual node execution text
- Python: Node-level streaming — each node's complete output is sent as one SSE message
- Impact: Frontend receives node output in chunks rather than character-by-character within a node

### 4. Python-Specific Extensions
- `POST /api/query/stream` — JSON body variant of stream search (Java has no equivalent)
- Python execution mode: Local subprocess only (Java supports Docker + AI simulation modes)

### 5. Missing Features (Planned)
- File upload for knowledge (multipart)
- Excel import for semantic models
- Logical relations CRUD
- Batch semantic model operations
- Model proxy configuration
- Token-level streaming within nodes

## Node Execution Differences

| Node | Java | Python | Notes |
|------|------|--------|-------|
| EvidenceRecall | ChromaDB hybrid search | ChromaDB vector only | Python lacks keyword hybrid strategy |
| TableRelation | Max 3 retries via dispatcher | Max 3 retries via conditional edge | Same semantics, different implementation |
| PlanExecutor | Validates + routes via Dispatcher | Validates + routes via conditional edge | Compatible semantics |
| SqlExecute | DDL detection + readonly enforcement | Direct SQL execution | Python should add DDL guard |
| PythonExecute | Docker/Local/AI-sim modes | Local subprocess only | Java has more execution modes |

## Future Plans

1. Add keyword + vector hybrid search for evidence recall
2. Add DDL detection guard in SQL execution
3. Support Docker-based Python execution
4. Add token-level streaming within long-running nodes
5. Full alignment of Knowledge/SemanticModel API paths
6. File upload support for knowledge documents
