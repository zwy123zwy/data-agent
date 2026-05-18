# 前端 Phase 1 实施总结 — 修改逻辑结构

**分支**: `feat/execution-panel`  
**提交**: 9 commits, 10 文件, +835 行  
**状态**: 全部 type-check 通过

---

## 一、数据流架构

```
SSE (text/event-stream)
  │
  ├─ data: {nodeName, text, textType, ...}
  │   └─ streamRequest.ts → handleNodeForExecution()
  │       ├─ 查 NODE_TO_EXECUTION 映射表 (17 entries)
  │       ├─ executionStore.openDrawer()      ← 首个 visible 节点
  │       ├─ executionStore.setThinking()      ← thinkingText 刷新
  │       ├─ executionStore.upsertRound()      ← agentName + roundIndex
  │       ├─ executionStore.addToolCall()      ← toolName (自动完成上一 tool)
  │       └─ executionStore.updateRoundStatus() ← finishRound 边界
  │
  ├─ event: complete
  │   └─ streamRequest.ts → onComplete
  │       ├─ executionStore.updateRoundStatus(lastAgent, 'done')
  │       └─ setTimeout(clearThinking, 1000)
  │
  ├─ event: error
  │   └─ streamRequest.ts → onError
  │       ├─ executionStore.stop()      ← 所有 running → skipped
  │       └─ executionStore.clearThinking()
  │
  └─ event: paused
      └─ streamRequest.ts → onPaused  ← 不改变 executionStore
```

## 二、组件树

```
AgentRun.tsx (3-zone flexbox)
  ├── ChatSessionSidebar         ← 不变
  ├── main (ChatArea)
  │   ├── ExecutionToggleButton  ← ★ 新增 (抽屉关闭时可见)
  │   ├── ThinkingBubble         ← ★ 新增 (单例, data-thinking-bubble)
  │   ├── ChatMessages           ← 不变
  │   ├── HumanFeedback          ← 不变
  │   └── ChatInput + StopButton ← Stop 链路扩展 (useAgentChat.handleStop)
  └── ExecutionDrawer            ← ★ 新增 (360px, transform slide-in)
      └── AgentRound             ← ★ 新增 (手风琴, 3 个 Round)
          └── ToolItem           ← ★ 新增 (图标 + 名称 + 状态)
```

## 三、核心文件职责

### 1. `src/stores/executionStore.ts` (新建, 165 行)

**类型**:
- `ToolStatus`: pending | running | done | error | skipped
- `RoundStatus`: pending | running | done | partial_failure | error | skipped
- `AgentName`: 'Explorer' | 'Analyst' | 'Reporter'
- `ToolCall`: { id, name, status, summary?, startedAt?, finishedAt? }
- `AgentRound`: { id, agentName, roundIndex, status, tools[] }

**关键行为**:
- `addToolCall()`: 新 tool 加入时自动将同 Round 内上一 running tool → done（V2.0 线性流水线，data.complete 在 SSE data 消息中永远为 false）
- `upsertRound()`: agentName 已存在则返回已有 round，不重复创建
- `stop()`: 所有 running → skipped，清空 thinking
- `reset()`: 恢复初始状态（在 useAgentChat.handleSend 中被调用）

### 2. `src/utils/streamRequest.ts` (修改, +157 行)

**新增内容** (插入在 sendGraphRequest 之前):
- `NODE_TO_EXECUTION` 映射表 (17 条, 覆盖当前全部 17 个 Java nodeName)
- `handleNodeForExecution()`: SSE data 消息 → executionStore 调用
- `truncateText()`: 文本截取工具函数

**注入点**:
- `onMessage` 中，error check 之后插入一行 `handleNodeForExecution(data.nodeName, ...)`
- `onComplete` 中，setState 之后注入 `updateRoundStatus` + `clearThinking` 延迟
- `onError` 中，setState 之后注入 `stop()` + `clearThinking()`

### 3. `src/views/AgentRun.tsx` (修改, +25 行)

**新增 import**: ExecutionDrawer, ThinkingBubble, useExecutionStore, ControlOutlined

**新增渲染**:
- `<ExecutionToggleButton>` — 抽屉关闭时在消息区右上角显示 "执行过程 ▸" 按钮
- `<ThinkingBubble />` — 在 ChatMessages 之前渲染
- `<ExecutionDrawer />` — 在 </main> 之后渲染

### 4. `src/hooks/useAgentChat.ts` (修改, +7 行)

- **handleSend**: `doStreamRequest()` 之前调用 `useExecutionStore.getState().reset()`
- **handleStop**: `closeStream()` 之前调用 `useExecutionStore.getState().stop()`

### 5. 四个新建展示组件

| 组件 | 行数 | 职责 |
|------|------|------|
| `ThinkingBubble.tsx` | 41 | 从 store 读 thinkingText/thinkingHint，空字符串不渲染，带 data-thinking-bubble 属性 |
| `ToolItem.tsx` | 116 | 10 种 tool emoji 映射 + 5 种 Ant Design 状态图标，hover 高亮，点击回调 |
| `AgentRound.tsx` | 176 | 折叠式 RoundHeader（状态图标+Tag+完成计数）+ Popover 详情 + ToolList |
| `ExecutionDrawer.tsx` | 132 | 360px 滑入面板，手风琴逻辑（undefined=自动/null=关闭/string=展开），全部 done 时显示 "✓ 执行完成" |

### 6. `src/types/graph.ts` (修改, +10 行)

GraphNodeResponse 新增 4 个可选字段（V3.0 预留，Phase 1 前端通过 nodeName 降级推断）:
- `agentName?`, `toolName?`, `toolStatus?`, `toolSummary?`

## 四、nodeName → UI 映射规则

| 后端 nodeName (SSE) | Agent Round | Tool | 思考文案 | 特殊操作 |
|---------------------|-------------|------|----------|----------|
| EvidenceRecallNode | Explorer (R1) | search_knowledge | 正在召回业务知识… | openDrawer |
| QueryEnhanceNode | Explorer | rewrite_query | 正在改写查询… | |
| SchemaRecallNode | Explorer | get_schema | 正在探查数据表结构… | |
| TableRelationNode | Explorer | find_relations | 正在分析表关联关系… | |
| FeasibilityAssessmentNode | — | — | 正在制定执行计划… | |
| PlannerNode | — | — | 正在制定执行计划… | finishRound: Explorer |
| PlanExecutorNode | — | — | 正在执行步骤… | |
| SqlGenerateNode | Analyst (R2) | text_to_sql | 正在生成 SQL 查询… | |
| SemanticConsistencyNode | Analyst | semantic_check | 正在校验语义一致性… | |
| SqlExecuteNode | Analyst | execute_sql | 正在执行 SQL 查询… | |
| PythonGenerateNode | Analyst | text_to_python | 正在生成分析代码… | |
| PythonExecuteNode | Analyst | run_python | 正在执行 Python 分析… | |
| PythonAnalyzeNode | Analyst | analyze_result | 正在解读分析结果… | |
| ReportGeneratorNode | Reporter (R3) | — | 正在生成分析报告… | finishRound: Analyst |
| HumanFeedbackNode | — | — | 等待人工确认… | |
| IntentRecognitionNode | — | — | (不展示) | |
| ChitchatNode | — | — | (不展示) | |
