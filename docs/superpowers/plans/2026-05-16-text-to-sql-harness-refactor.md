# Text-to-SQL Agent Harness 重构

> 使用 superpowers:subagent-driven-development 执行

**Goal:** WorkflowNode 基类化 — 每个节点自声明 I/O/SSE，Controller 不再窥探节点内部

**Architecture:** 不改 LangGraph 拓扑，只在节点层加 Harness 元数据。Controller 改读通用 `sse_output` key

**Files:** 新建 1 + 修改 19 = 20 个文件

---

### Task 1: WorkflowNode 基类

**Create:** `app/workflows/node_base.py`

- SSEPayload dataclass
- WorkflowNode ABC（name/description/requires/provides/execute/format_sse/__call__）

### Task 2-17: 改造 16 个节点

每个节点：函数 → WorkflowNode 子类，加注释 + format_sse()

### Task 18: 简化 Controller

**Modify:** `app/api/streaming_graph_controller.py`

- 移除 _NODE_MSG dict (L82-105)
- 移除 260 行 if/elif (L382-644)
- 替换为读 sse_output 的通用循环

### Task 19: 更新 __init__.py

**Modify:** `app/workflows/nodes/__init__.py`

### Task 20: 清理冗余 + CHANGELOG

**Remove:** `app/workflows/node_messages.py`
**Modify:** `CHANGELOG.md`
