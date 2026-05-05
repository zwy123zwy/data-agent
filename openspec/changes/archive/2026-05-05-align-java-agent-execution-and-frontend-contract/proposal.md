# Align Java Agent Execution And Frontend Contract

## Background

当前项目目标是让 `python-agent-v2` 对齐 Java 版 `DataAgent/data-agent-management` 的智能体执行能力，并能被现有前端 `DataAgent/data-agent-frontend` 无缝调用。

现状：

- 前端会话页实际使用 `GET /api/stream/search`，并按 Java 版 `GraphNodeResponse` 解析 SSE 数据。
- Java 版 Agent 执行链路为 `GraphController → GraphServiceImpl → CompiledGraph.stream() → StateGraph nodes → GraphNodeResponse SSE`。
- Python 版已有相似 Graph 执行流程，但部分协议、节点命名、SSE 格式、HumanFeedback 恢复方式、前后端协同细节仍需严格对齐。

## Goal

让 Python 版达到以下结果：

1. 前端无需大改即可切换到 Python 后端。
2. Python 版 `/api/stream/search` 返回格式与 Java 版 `GraphNodeResponse` 兼容。
3. Python 版 Agent 执行节点能力、路由条件、重试/恢复语义与 Java 版一致或有明确差异说明。
4. 会话、消息、报告、标题更新、HumanFeedback 等前后端协同链路稳定。
5. 建立对齐验收用例和节点级指标，保证后续迭代可回归。

## Non Goals

- 不重写前端整体交互。
- 不要求 Python 内部技术栈完全复制 Java，只要求行为和协议兼容。
- 不在本阶段新增全新的业务分析能力，优先补齐 Java 已有能力。

## Key Compatibility Targets

### Stream API

Java frontend expects:

```http
GET /api/stream/search?agentId=&threadId=&query=&humanFeedback=&humanFeedbackContent=&rejectedPlan=&nl2sqlOnly=
```

SSE data should be JSON compatible with:

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

Completion should emit:

```text
event: complete
data: {"complete": true, ...}
```

Error should emit:

```text
event: error
data: {"error": true, "text": "...", ...}
```

### Agent Execution

Python should align to Java execution semantics:

```text
IntentRecognition
→ EvidenceRecall / KnowledgeRecall
→ QueryEnhance / QueryRewrite
→ SchemaRecall
→ TableRelation
→ FeasibilityAssessment
→ Planner
→ PlanExecutor
→ SQL / Python / HumanFeedback / Report
```

### Frontend Coordination

Frontend expects:

- Session list, create, clear APIs.
- Message list and save APIs.
- Session title update SSE.
- HTML report download API.
- Stream continuation with same `threadId`.
- HumanFeedback approve/reject resume using `humanFeedbackContent` and `rejectedPlan`.

