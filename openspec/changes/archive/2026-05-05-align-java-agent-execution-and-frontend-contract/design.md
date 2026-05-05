# Design: Python-Java Agent Execution Alignment

## Architecture Overview

Python agent uses LangGraph StateGraph with identical topology to Java's Spring AI StateGraph.

```
START → IntentRecognition
  → (chitchat) END
  → (data_analysis) KnowledgeRecall → QueryRewrite → SchemaRecall
    → TableRelation (含重试) → FeasibilityAssessment
      → (不可行) END
      → (可行) Planner → PlanExecutor (循环调度入口)
        ├→ SQL_GENERATE → SemanticConsistency → SQL_EXECUTE → PlanExecutor
        ├→ PYTHON_GENERATE → PYTHON_EXECUTE → PYTHON_ANALYZE → PlanExecutor
        ├→ REPORT_GENERATOR → END
        └→ HUMAN_FEEDBACK → (approve) PlanExecutor / (reject) Planner
```

## Key Design Decisions

### 1. SSE Protocol Compatibility

**Decision:** Use plain `data:` lines for node output, `event:` prefix for lifecycle events.
**Rationale:** Java uses Spring `ServerSentEvent<GraphNodeResponse>`. Python mimics this with manual SSE formatting functions (`_format_sse_data`, `_format_sse_event`). Frontend `EventSource.onmessage` receives plain data messages, `addEventListener('complete', ...)` receives named events.

### 2. Node Name Mapping

**Decision:** Map Python internal names to Java `Constant.java` node names at the SSE emission layer.
**Rationale:** Frontend uses `nodeName` to decide how to render content blocks. Python keeps its own internal naming but translates to Java-compatible names when sending to frontend.

### 3. HumanFeedback via LangGraph interrupt()

**Decision:** Use LangGraph's native `interrupt()` mechanism instead of mimicking Java's `interruptBefore()` + paused state.
**Rationale:** LangGraph's `interrupt()` is the idiomatic way to pause graph execution. The resume flow uses `Command(resume=...)` with identical semantics to Java's `CompiledGraph.resume()`.

### 4. PlanExecutor Cycle Topology

**Decision:** Use conditional edges to route from PlanExecutor to SQL/Python/Report/HumanFeedback branches, with edges back to PlanExecutor for the next step.
**Rationale:** This exactly mirrors Java's PlanExecutorDispatcher pattern. Each sub-branch returns to PlanExecutor, which checks if all steps are done.

### 5. Internal Nodes Not Streamed

**Decision:** RAG, Schema, TableRelation, Feasibility, Planner, SemanticConsistency nodes execute silently.
**Rationale:** Java only streams from specific nodes. Exposing internal nodes would confuse the frontend's node-based message grouping.

### 6. TextType Constants

**Decision:** Define Python module-level constants matching Java's `TextType` enum.
**Rationale:** Frontend uses TextType to decide rendering components. Values must exactly match Java's `SQL`, `JSON`, `HTML`, `MARK_DOWN`, `RESULT_SET`, `PYTHON`, `TEXT`.

## Data Flow

### Request → State
```
GET /api/stream/search?agentId=&query=&threadId=...
  → _build_initial_state() → WorkflowState{agent_id, user_query, ...}
```

### Node Execution → SSE
```
LangGraph astream() → (node_name, state_update)
  → NODE_NAME_MAP[node_name] → Java node name
  → _build_graph_response() → GraphNodeResponse dict
  → _format_sse_data() / _format_sse_event() → SSE bytes
```

### HumanFeedback Resume
```
1st request: humanFeedback=true → interrupt() → SSE human_feedback data → stream ends
2nd request: threadId=xxx&humanFeedbackContent=...&rejectedPlan=...
  → Command(resume={action, reason}) → human_feedback_node continues → PlanExecutor/Planner
```

## Error Handling

- Node-level errors: Caught in node, written to `state["error"]`, routed to END
- SSE-level errors: Wrapped in `event: error` SSE message
- Client disconnect: `asyncio.CancelledError` caught, resources released silently
- Plan validation failure: Max 3 repair attempts, then END
- SQL retry: Max `settings.max_sql_retry_count` retries
- Python fallback: After max retries, skips to analyze with fallback message
