# Python-Java Agent Execution Protocol Alignment

## SSE Stream Protocol

Python `GET /api/stream/search` fully aligns with Java `GraphController.streamSearch()`.

### Request Parameters

| Parameter | Type | Java | Python | Status |
|-----------|------|------|--------|--------|
| `agentId` | int | ✅ | ✅ | Aligned |
| `query` | string | ✅ | ✅ | Aligned |
| `threadId` | string | ✅ | ✅ | Aligned |
| `humanFeedback` | bool | ✅ | ✅ | Aligned |
| `humanFeedbackContent` | string | ✅ | ✅ | Aligned |
| `rejectedPlan` | bool | ✅ | ✅ | Aligned |
| `nl2sqlOnly` | bool | ✅ | ✅ | Aligned |

### SSE Data Format

Python sends `GraphNodeResponse` JSON on plain SSE data lines (no `event:` prefix), compatible with frontend `EventSource.onmessage`:

```json
{
  "agentId": "1",
  "threadId": "uuid",
  "nodeName": "SqlGenerateNode",
  "textType": "SQL",
  "text": "SELECT ...",
  "error": false,
  "complete": false
}
```

### SSE Events

| Event | When | Format |
|-------|------|--------|
| (none / data:) | Node output | `data: {GraphNodeResponse JSON}\n\n` |
| `event: complete` | Workflow finished | `event: complete\ndata: {"complete":true,...}\n\n` |
| `event: error` | Workflow error | `event: error\ndata: {"error":true,...}\n\n` |

### TextType Values

Aligned with Java `TextType` enum and frontend:
- `SQL` — SQL statement
- `JSON` — JSON data
- `HTML` — HTML report
- `MARK_DOWN` — Markdown content
- `RESULT_SET` — Query result set
- `PYTHON` — Python code
- `TEXT` — Plain text / status message

### Node Name Mapping

Python internal names → Java node names (frontend uses these for grouping):

| Python Node | Java NodeName |
|-------------|---------------|
| `intent_recognition` | `IntentRecognitionNode` |
| `knowledge_recall` | `EvidenceRecallNode` |
| `query_rewrite` | `QueryEnhanceNode` |
| `schema_recall` | `SchemaRecallNode` |
| `table_relation` | `TableRelationNode` |
| `feasibility` | `FeasibilityAssessmentNode` |
| `planner` | `PlannerNode` |
| `plan_executor` | `PlanExecutorNode` |
| `sql_generate` | `SqlGenerateNode` |
| `semantic_consistency` | `SemanticConsistencyNode` |
| `sql_execute` | `SqlExecuteNode` |
| `python_generate` | `PythonGenerateNode` |
| `python_execute` | `PythonExecuteNode` |
| `python_analyze` | `PythonAnalyzeNode` |
| `report_generator` | `ReportGeneratorNode` |
| `human_feedback` | `HumanFeedbackNode` |

### Internal Nodes (Not Streamed to Frontend)

The following nodes execute silently (no SSE output), matching Java behavior:
- `knowledge_recall` (EvidenceRecallNode)
- `query_rewrite` (QueryEnhanceNode)
- `schema_recall` (SchemaRecallNode)
- `table_relation` (TableRelationNode)
- `feasibility` (FeasibilityAssessmentNode)
- `planner` (PlannerNode)
- `plan_executor` (PlanExecutorNode)
- `semantic_consistency` (SemanticConsistencyNode)
- `python_execute` (PythonExecuteNode)

## Python Extension: POST /api/query/stream

Python provides an additional `POST /api/query/stream` endpoint using JSON body (`QueryRequest` schema). It produces identical SSE output to `GET /api/stream/search`.

**Use cases:** internal calls, testing, non-browser clients.

**Frontend main path remains `GET /api/stream/search`.**

## HumanFeedback Resume Protocol

1. Initial request includes `humanFeedback=true` (or `human_feedback=true` in body)
2. When plan is ready for review, SSE sends HumanFeedbackNode output with plan details
3. Graph pauses (LangGraph `interrupt()`)
4. User approves/rejects via UI
5. Resume: `GET /api/stream/search?threadId=<same>&humanFeedbackContent=<feedback>&rejectedPlan=<bool>`
6. On approve → PlanExecutor continues
7. On reject → Planner regenerates (max 3 rejections, then ends)
