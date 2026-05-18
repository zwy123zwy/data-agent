# Frontend Interaction Design — 多 Agent 执行可视化

**日期**: 2026-05-18  
**状态**: DRAFT (审计修订 V1.1)  
**关联**: `2026-05-18-multi-agent-architecture-design.md` (后端架构 V3.0)

> **版本说明**: 本文档设计目标态（后端 V3.0 — Explorer/Analyst/Reporter 三 Agent ReAct）。当前后端为 V2.0（16 节点固定流水线），§7 提供了 V2.0 降级映射表。SSE 协议字段统一使用当前后端实际发送的名称（Java CamelCase `*Node` 后缀）。

---

## 1. 设计目标

将多 Agent 协作过程（Explorer → Analyst → Reporter）以「思考气泡 + 侧边执行面板」形式在前端可视化：

- **对话区**: 用户提问 → 🧠 思考气泡（单例，内容随节点切换刷新）→ 🤖 AI 回复气泡
- **执行面板**: 右侧抽屉，执行开始时自动滑入，以 Round 为单位展示每个 Agent 的 tool 调用时序
- **参考**: 字节跳动 DataAgent 3.0 交互模式
- **兼容**: 当前后端 V2.0 16 节点模式通过 §7 映射表降级运行

---

## 2. 页面布局

### 方案 B: 两栏 + 可展开抽屉

```
┌──────────┬────────────────────────┬──────────────┐
│ Sidebar  │    ChatArea            │  Execution   │
│ 48/260px │    flex: 1             │  Drawer      │
│          │                        │  360px       │
│ 💬       │  ┌─ChatHeader───┐      │  slide-in    │
│          │  │ 标题 + 执行按钮│      │  from right  │
│ 会话1    │  ├──────────────┤      │              │
│ 会话2    │  │ 💬 UserBubble│      │  ● Round 1   │
│          │  │ 🧠 思考中... │      │    Explorer   │
│          │  │ 🤖 AIBubble  │      │  ● Round 2   │
│          │  ├──────────────┤      │    Analyst    │
│          │  │ 输入区       │      │  ○ Round 3   │
│          │  └──────────────┘      │    Reporter   │
└──────────┴────────────────────────┴──────────────┘
```

### 规则

- **默认状态**: 左侧会话列表 + 对话区，执行面板隐藏
- **执行开始时**: 抽屉从右侧滑入（`transform: translateX` + `transition: 0.3s`），宽度 360px
- **执行结束后**: 抽屉保持可见，用户点击 ✕ 手动关闭
- **简单问题（chitchat）**: 不打开抽屉

### 响应式

- `>= 1440px`: 三区域完整展示 (Sidebar 260px + Chat + Drawer 360px)
- `1024px - 1439px`: Sidebar 折叠为 48px 图标模式，Drawer 320px
- `< 1024px`: Drawer 覆盖 ChatArea（overlay 模式），点击遮罩关闭

---

## 3. 组件树

```
AgentRun (page)
├── ChatSessionSidebar              — 左侧会话列表 (48px collapsed / 260px expanded)
│   ├── SidebarToggle               — 展开/折叠按钮
│   ├── SessionList                 — 会话列表
│   └── NewSessionButton            — 新建会话
│
├── ChatArea (main)
│   ├── ChatHeader                  — 会话标题 + 状态指示
│   │   ├── SessionTitle            — 当前会话名
│   │   └── ExecutionToggleButton   — 「⚙️ 执行过程 ▸」按钮 (抽屉关闭时可见)
│   │
│   ├── ChatMessages                — 对话流 (overflow-y: auto, scroll-behavior: smooth)
│   │   ├── UserBubble              — 用户消息 (蓝色, 右对齐, border-radius: 12px 12px 0 12px)
│   │   ├── ThinkingBubble          — 🧠 思考气泡 (单例, 灰底, 左对齐)
│   │   │   └── ThinkingContent     — 内容随 Agent 切换实时刷新
│   │   └── AIBubble                — AI 回复 (Markdown / HTML Report / Table / ResultSet)
│   │
│   └── ChatInput                   — 底部输入区
│       ├── TextArea                — 输入框
│       ├── SendButton              — 发送按钮
│       └── StopButton              — 停止按钮 (执行中替换发送按钮)
│
└── ExecutionDrawer                 — 右侧抽屉 (360px)
    ├── DrawerHeader                — 「⚙️ 执行过程」标题 + ✕ 关闭 + Round 进度
    └── AgentRoundList              — Round 列表 (overflow-y: auto)
        └── AgentRound (collapsible)
            ├── RoundHeader         — ● Round N · AgentName (状态色: 绿=完成 / 蓝=进行中 / 灰=待执行)
            ├── ToolList            — 展开后的 tool 清单
            │   └── ToolItem        — 🔍 get_schema ✓ / ⚡ execute_sql ⟳
            └── RoundDetailPopover  — 点击弹出 (输入/输出/tool 调用日志)
```

---

## 4. 思考气泡 (ThinkingBubble)

### 行为

- **单例模式**: 对话区始终最多一个思考气泡
- **内容刷新**: 当前 Agent 切换时，气泡内文案刷新（如 `正在探查数据结构…` → `正在生成 SQL…`），无过渡动画
- **生命周期**:
  1. 首个 workflow node 产出内容 → 思考气泡出现
  2. 每次 `nodeName` 变化 → `thinkingText` 更新
  3. `ReportGenerator` 完成 → AI 回复气泡渲染后 1 秒，思考气泡淡出 (`opacity: 0, transition: 0.5s`)

### 文案映射

`thinkingText` 由 SSE `nodeName` 字段驱动（后端发送 Java CamelCase 名称）。同一 Agent 下多个节点共享相同文案，`thinkingHint`（副文案）由当前 tool 名动态拼接。

| SSE nodeName (实际值) | Agent Round | thinkingText |
|----------------------|-------------|-------------|
| `EvidenceRecallNode` | Explorer | 正在召回业务知识… |
| `QueryEnhanceNode` | Explorer | 正在改写查询… |
| `SchemaRecallNode` | Explorer | 正在探查数据表结构… |
| `TableRelationNode` | Explorer | 正在分析表关联关系… |
| `FeasibilityAssessmentNode` | — | 正在制定执行计划… |
| `PlannerNode` | — | 正在制定执行计划… |
| `SqlGenerateNode` | Analyst | 正在生成 SQL 查询… |
| `SemanticConsistencyNode` | Analyst | 正在校验语义一致性… |
| `SqlExecuteNode` | Analyst | 正在执行 SQL 查询… |
| `PythonGenerateNode` | Analyst | 正在生成分析代码… |
| `PythonExecuteNode` | Analyst | 正在执行 Python 分析… |
| `PythonAnalyzeNode` | Analyst | 正在解读分析结果… |
| `ReportGeneratorNode` | Reporter | 正在生成分析报告… |
| `HumanFeedbackNode` | — | 等待人工确认… |
| `ChitchatNode` | — | (不展示思考气泡) |

#### 重试文案

SQL 生成/执行可能重试（最多 10 次），重试时 `thinkingHint` 显示当前尝试次数：

```
🧠 正在生成 SQL 查询…
   第 3 次尝试…
```

### UI 样式

```
┌─────────────────────────────────────────────┐
│ 🧠 正在探查数据表结构…                      │
│    调用 get_schema → 获取到 5 张表           │  ← thinkingHint (副文案, 可选)
└─────────────────────────────────────────────┘
  background: var(--bg-secondary)
  border: 1px solid var(--border)
  border-radius: 12px
  max-width: 85%
  padding: 10px 14px
  font-size: 13px
  .thinkingTitle: color var(--accent), margin-bottom 4px
  .thinkingHint:  color var(--text-secondary), font-size 12px
```

---

## 5. 执行面板 (ExecutionDrawer)

### 生命周期

- **滑入**: `drawerVisible` 由 `EvidenceRecallNode` 或 `SchemaRecallNode` 的首个 SSE 消息触发 → `setDrawerVisible(true)`
- **关闭**: 仅用户点击 ✕ 按钮 → `setDrawerVisible(false)`
- **不自动关闭**: 执行结束后抽屉保持可见，顶部出现 `✓ 执行完成` 提示，下次 `reset()` 清空后重新点亮
- **chitchat**: 不打开抽屉，不产生 Round

### 面板内容 — AgentRound 分组规则

**V3.0 目标**: 每个 ReAct Agent 执行周期对应一个 Round。

**V2.0 兼容**: 当前 16 个线性节点按职责聚合为 3 个 Round：

- **Round 1 · Explorer**: `EvidenceRecallNode` → `QueryEnhanceNode` → `SchemaRecallNode` → `TableRelationNode` → `FeasibilityAssessmentNode` → `PlannerNode`（召回知识 + 改写查询 + 探查表结构 + 表关联 + 可行性 + 制定计划），`PlannerNode` 完成后 Explorer round done
- **Round 2 · Analyst**: `SqlGenerateNode` → `SemanticConsistencyNode` → `SqlExecuteNode` → `PythonGenerateNode` → `PythonExecuteNode` → `PythonAnalyzeNode`（SQL/Python 生成与执行），结束时标记 done
- **Round 3 · Reporter**: `ReportGeneratorNode`（生成报告）

`PlanExecutorNode` 和 `FeasibilityAssessmentNode`、`PlannerNode` 作为编排节点，不产生 tool 条目，但 `PlannerNode` 触发 Explorer → Analyst 的 Round 切换。

```
Round 1 · Explorer    ● 已完成 (绿色)
  ├── 🔍  get_schema         ✓  3 tables
  ├── 📚  search_knowledge   ✓  2 results
  └── 🔗  find_relations     ✓  4 relations

Round 2 · Analyst     ● 执行中 (蓝色, 脉冲动画)
  ├── 📝  text_to_sql        ✓  SELECT ...
  ├── ⚡  execute_sql         ⟳ 执行中...
  └── 🐍  run_python          ○ 等待

Round 3 · Reporter     ○ 待执行 (灰色)
```

### Round 状态色

| 状态 | 颜色 | 指示器 |
|------|------|--------|
| 完成 | `#52c41a` (绿) | ✓ |
| 执行中 | `var(--accent)` (蓝) | ⟳ 脉冲动画 |
| 部分失败 | `#faad14` (黄) | ⚠ + 部分 tool 成功部分失败 |
| 失败 | `#ff4d4f` (红) | ✕ + tool 摘要显示错误信息 |
| 待执行 | `var(--border)` (灰) | ○ |
| 跳过 | `var(--text-secondary)` | — |

### 执行完成后的面板表现

- 所有 Round 完成后，面板顶部出现一行提示：`✓ 执行完成`（灰色 `var(--text-secondary)`，居中，font-size 12px）
- Round 列表保持正常颜色，不做整体置灰
- 下次新请求开始时，`reset()` 清空 Round 列表，提示消失

### 异常状态处理

#### Tool 失败
- 对应 ToolItem 标记为红色 ✕，显示错误摘要（如 `execute_sql ✕ 语法错误: near "SELECTT"`）
- Round 状态变为「部分失败」(黄色 `#faad14`)
- 流程可能进入重试 → 新的 tool 条目追加到同一 Round
- 多次重试失败后流程终止 → Round 保持红色

#### SSE 断连重连
- 断连期间产生的 Round/Tool 状态无法恢复（SSE 是单向流）
- 重连后如果执行仍在继续（`event: complete` 未收到），抽屉保持上次状态，后续 SSE 事件继续追加
- 如果已收到 `event: complete` 或 `event: error`，抽屉显示最终状态

#### 用户停止 (StopButton)
- `EventSource.close()` → SSE 连接断开
- 正在 `running` 的 ToolItem 标记为 `skipped`（灰色 `—`）
- 正在 `running` 的 Round 标记为 `skipped`
- 抽屉保持可见（用户可回顾已执行步骤）
- 思考气泡立即消失

### 节点交互

**1. 点击 RoundHeader → 展开/折叠 ToolList**
- 默认: 当前执行中的 Round 展开，已完成的折叠
- 手风琴: 同一时间只展开一个 Round
- ToolList 以 200ms 动画展开 (`max-height` transition)

**2. 点击 ToolItem → 对话区滚动定位**
- 触发 `scrollToThinkingBubble()` → ChatMessages 滚动到对应的思考气泡位置
- 如果该 tool 对应的思考气泡已被后续覆盖，则高亮最近的 AI 消息中该 tool 产出的片段

**3. 点击 RoundHeader 右侧 ℹ️ 图标 → 弹出详情 Popover**
- Popover 内容:
  - **输入**: 该 Agent 接收的 instruction + context 摘要
  - **输出**: Agent 完成后的 summary / artifact 预览
  - **Tool 调用日志**: 每个 tool 的 input/output/耗时
- Popover 定位: 相对于 RoundHeader 右侧，max-width 400px
- 关闭: 点击 Popover 外部或 ✕ 按钮

---

## 6. 状态管理 (Zustand Store 扩展)

### executionStore (新)

```typescript
interface ToolCall {
  id: string
  name: string           // get_schema / execute_sql / ...
  status: 'pending' | 'running' | 'done' | 'error'
  summary?: string       // "3 tables" / "SELECT ..."
  output?: unknown       // tool 返回的完整数据 (用于 Popover)
  startedAt?: number
  finishedAt?: number
}

interface AgentRound {
  id: string
  agentName: string      // Explorer / Analyst / Reporter
  roundIndex: number
  status: 'pending' | 'running' | 'done' | 'partial_failure' | 'error' | 'skipped'
  tools: ToolCall[]
  input?: string         // Agent 接收的 instruction
  output?: string        // Agent 完成的 summary
}

interface ExecutionState {
  // 抽屉
  drawerVisible: boolean
  openDrawer: () => void
  closeDrawer: () => void

  // Round 管理
  rounds: AgentRound[]
  activeRoundIndex: number
  upsertRound: (agentName: string, roundIndex: number) => AgentRound
  updateRoundStatus: (agentName: string, status: AgentRound['status']) => void
  addToolCall: (agentName: string, tool: ToolCall) => void
  updateToolCall: (agentName: string, toolId: string, update: Partial<ToolCall>) => void

  // 思考气泡
  thinkingText: string
  thinkingHint: string
  setThinking: (text: string, hint?: string) => void
  setThinkingHint: (hint: string) => void
  clearThinking: () => void

  // Tool 完成追踪
  lastAgentName: string | null
  finishLastToolCall: (agentName: string) => void
  updateLastRunningToolStatus: (status: ToolCall['status']) => void
  updateLastRunningRoundStatus: (status: AgentRound['status']) => void

  // 停止/重置
  stop: () => void          // 停止按钮触发 — 标记 running → skipped, 清除 thinking
  reset: () => void         // 新请求开始前重置所有状态
}

`stop()` 实现逻辑:

```typescript
stop: () => {
  // 将所有 running 状态的 tool 标记为 skipped
  set((state) => ({
    rounds: state.rounds.map((round) => ({
      ...round,
      status: round.status === 'running' ? 'skipped' : round.status,
      tools: round.tools.map((tool) => ({
        ...tool,
        status: tool.status === 'running' ? 'skipped' : tool.status,
      })),
    })),
    thinkingText: '',
    thinkingHint: '',
  }))
}
```

### 用法: SSE 事件处理

```typescript
// handleSSEMessage 中的映射逻辑
// 注意: nodeName 是后端 NODE_NAME_MAP 映射后的 Java CamelCase 名称
// 详见 streaming_graph_controller.py NODE_NAME_MAP

switch (payload.nodeName) {
  // ===== Round 1: Explorer (召回 + 改写 + 探查 + 关联) =====
  case 'EvidenceRecallNode':
    execStore.openDrawer()
    execStore.setThinking('正在召回业务知识…')
    execStore.upsertRound('Explorer', 1)
    execStore.addToolCall('Explorer', { name: 'search_knowledge', status: 'running' })
    break

  case 'QueryEnhanceNode':
    execStore.setThinking('正在改写查询…')
    execStore.addToolCall('Explorer', { name: 'rewrite_query', status: 'running' })
    break

  case 'SchemaRecallNode':
    execStore.setThinking('正在探查数据表结构…')
    execStore.addToolCall('Explorer', { name: 'get_schema', status: 'running' })
    break

  case 'TableRelationNode':
    execStore.setThinking('正在分析表关联关系…')
    execStore.addToolCall('Explorer', { name: 'find_relations', status: 'running' })
    break

  // ===== 编排节点 (不产生 tool 条目) =====
  case 'FeasibilityAssessmentNode':
    execStore.setThinking('正在制定执行计划…')
    break

  case 'PlannerNode':
    execStore.setThinking('正在制定执行计划…')
    execStore.updateRoundStatus('Explorer', 'done')
    break

  // ===== 循环调度器 (不产生 tool 条目) =====
  case 'PlanExecutorNode':
    // 每次出现代表新一轮 step 分发, 不更新 UI
    break

  // ===== Round 2: Analyst (SQL/Python 生成与执行) =====
  case 'SqlGenerateNode':
    execStore.setThinking('正在生成 SQL 查询…')
    execStore.upsertRound('Analyst', 2)
    execStore.addToolCall('Analyst', { name: 'text_to_sql', status: 'running' })
    break

  case 'SemanticConsistencyNode':
    execStore.setThinking('正在校验语义一致性…')
    execStore.addToolCall('Analyst', { name: 'semantic_check', status: 'running' })
    break

  case 'SqlExecuteNode':
    execStore.setThinking('正在执行 SQL 查询…')
    execStore.addToolCall('Analyst', { name: 'execute_sql', status: 'running' })
    break

  case 'PythonGenerateNode':
    execStore.setThinking('正在生成分析代码…')
    execStore.addToolCall('Analyst', { name: 'text_to_python', status: 'running' })
    break

  case 'PythonExecuteNode':
    execStore.setThinking('正在执行 Python 分析…')
    execStore.addToolCall('Analyst', { name: 'run_python', status: 'running' })
    break

  case 'PythonAnalyzeNode':
    execStore.setThinking('正在解读分析结果…')
    execStore.addToolCall('Analyst', { name: 'analyze_result', status: 'running' })
    break

  // ===== Round 3: Reporter =====
  case 'ReportGeneratorNode':
    execStore.setThinking('正在生成分析报告…')
    execStore.upsertRound('Reporter', 3)
    execStore.updateRoundStatus('Analyst', 'done')
    break

  // ===== Human Feedback =====
  case 'HumanFeedbackNode':
    execStore.setThinking('等待人工确认…')
    // 输入区出现确认/拒绝按钮, 抽屉暂停动画
    break

  // ===== Chitchat: 不展示任何执行过程 =====
  case 'ChitchatNode':
    // 不打开抽屉, 不展示思考气泡
    break
}

// 每个 node SSE 消息的 complete 为 true → 更新对应 tool 状态为 'done'
// 注意: 此处的 payload.complete 是 GraphNodeResponse 的 complete 字段 (节点级完成),
//       不是 SSE event: complete (工作流级完成)
if (payload.complete && execStore.lastAgentName) {
  execStore.finishLastToolCall(execStore.lastAgentName)
}

// 当 textType 为 TEXT 且非完成态 → 尝试提取 tool 结果摘要作为 thinkingHint
if (payload.textType === 'TEXT' && !payload.complete) {
  execStore.setThinkingHint(truncateText(payload.text, 80))
}
```

#### 生命周期事件处理（独立于 nodeName switch）

当前前端使用 `fetch + ReadableStream` 解析 SSE (见 `src/services/graph.ts`)。流中通过 `event: <type>` 行前缀区分事件类型，DATA 消息通过 `data: <json>` 行进入 `nodeName` switch：

```typescript
// 在 ReadableStream 解析循环中:
let currentEvent = 'message' // 默认

// 逐行读取
if (line.startsWith('event: ')) {
  currentEvent = line.slice(7).trim()  // complete | error | paused
} else if (line.startsWith('data: ')) {
  const payload = JSON.parse(line.slice(6))

  switch (currentEvent) {
    case 'message':
      // 进入 payload.nodeName switch (见上方)
      handleNodeMessage(payload)
      break

    case 'complete':
      // 思考气泡在 AI 回复渲染后 1s 淡出
      setTimeout(() => execStore.clearThinking(), 1000)
      // 抽屉保留, Round 状态不变 (已全部 done)
      break

    case 'error':
      // 最后一个 running 的 Tool/Round 标记为 error
      execStore.updateLastRunningToolStatus('error')
      execStore.updateLastRunningRoundStatus('error')
      break

    case 'paused':
      // 等待人工确认 — 抽屉和思考气泡保持当前状态
      // 输入区出现确认/拒绝按钮 (现有 HumanFeedback 逻辑不变)
      break
  }

  currentEvent = 'message' // 重置
}
```

`truncateText` 工具函数:

```typescript
/** 截取文本首行，限制 maxLen 字符，用于 tool 摘要展示 */
function truncateText(text: string, maxLen: number = 80): string {
  const firstLine = text.split('\n')[0].trim()
  return firstLine.length > maxLen
    ? firstLine.slice(0, maxLen) + '...'
    : firstLine
}
```

---

## 7. SSE 事件 → UI 映射表

### 7.1 V2.0 当前态（16 节点 → 3 Round 降级映射）

前端不区分 V2.0/V3.0——统一按 `nodeName` + `agentName`（可选字段）驱动 UI。

| SSE nodeName (实际值) | 思考气泡 | 执行面板 |
|----------------------|---------|---------|
| `IntentRecognitionNode` | — (内部判断) | — |
| `ChitchatNode` | — | 不打开抽屉 |
| `EvidenceRecallNode` | 🧠 正在召回业务知识… | 打开抽屉, +Round 1 Explorer, +tool: search_knowledge |
| `QueryEnhanceNode` | 🧠 正在改写查询… | +tool: rewrite_query |
| `SchemaRecallNode` | 🧠 正在探查数据表结构… | +tool: get_schema |
| `TableRelationNode` | 🧠 正在分析表关联关系… | +tool: find_relations |
| `FeasibilityAssessmentNode` | 🧠 正在制定执行计划… | — |
| `PlannerNode` | 🧠 正在制定执行计划… | Explorer round → done (切换到 Analyst) |
| `PlanExecutorNode` | — | — (编排节点, 不产生 UI 变化) |
| `SqlGenerateNode` | 🧠 正在生成 SQL 查询… | +Round 2 Analyst, +tool: text_to_sql |
| `SemanticConsistencyNode` | 🧠 正在校验语义一致性… | +tool: semantic_check |
| `SqlExecuteNode` | 🧠 正在执行 SQL 查询… | +tool: execute_sql |
| `PythonGenerateNode` | 🧠 正在生成分析代码… | +tool: text_to_python |
| `PythonExecuteNode` | 🧠 正在执行 Python 分析… | +tool: run_python |
| `PythonAnalyzeNode` | 🧠 正在解读分析结果… | +tool: analyze_result |
| `ReportGeneratorNode` | 🧠 正在生成分析报告… | +Round 3 Reporter, Analyst round → done |
| `HumanFeedbackNode` (interrupt) | ⏸️ 等待人工确认… | 抽屉暂停动画, 输入区出现确认/拒绝按钮 |
| `event: complete` | 淡出消失 (AI 回复出现后 1s) | 抽屉保持, 顶部显示 `✓ 执行完成` 提示 |
| `event: error` | 显示错误提示 | 抽屉保留, 失败 Round 变红 |
| `event: paused` | 更新为等待确认 | 暂停状态显示 |

### 7.2 V3.0 目标态 (Explorer/Analyst/Reporter Agent 原生支持)

当后端升级到 V3.0 ReAct Agent 架构后，SSE payload 将包含 `agentName` + `toolName` 字段，前端直接映射：

```json
{
  "agentId": "1",
  "threadId": "uuid",
  "nodeName": "Explorer",
  "textType": "TEXT",
  "text": "正在获取数据表结构...",
  "agentName": "Explorer",
  "toolName": "get_schema",
  "toolStatus": "running",
  "toolSummary": "发现 5 张表",
  "error": false,
  "complete": false
}
```

此时前端 switch 可简化为由 `agentName` 驱动 Round 分组，`toolName` + `toolStatus` 直接驱动 ToolItem 增删改，无需硬编码 16 个 nodeName case。

### 7.3 需要后端适配的 SSE 字段

当前 SSE 协议输出 `nodeName` + `textType` + `text` + `error` + `complete`。为支持执行面板精细化展示，建议新增可选字段（V2.0 → V3.0 渐进升级）：

```json
{
  "agentName": "Explorer",
  "toolName": "get_schema",
  "toolStatus": "running",
  "toolSummary": "发现 5 张表"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `agentName` | string | 否 | 所属 Agent (Explorer/Analyst/Reporter)，V3.0 后必填 |
| `toolName` | string | 否 | 当前 tool 名称 |
| `toolStatus` | string | 否 | pending / running / done / error |
| `toolSummary` | string | 否 | tool 结果摘要（单行，< 80 字符） |

> **前端 graceful degrade**: 无这些字段时，通过 `nodeName` 查 §7.1 映射表确定 Round 归属和 tool 名称。

---

## 8. 实现分工

### 前端

| 层 | 负责 | 关键文件 |
|---|------|---------|
| 状态管理 | 新增 `executionStore` (Zustand)，含 Round/Tool 管理 + 思考气泡 + stop/reset | `src/stores/executionStore.ts` |
| SSE 解析 | 在现有 `streamRequest.ts` 中增加 §6 节点名映射逻辑 | `src/utils/streamRequest.ts` |
| 思考气泡 | 新增 `ThinkingBubble.tsx`（单例模式，内容随 nodeName 刷新） | `src/components/run/ThinkingBubble.tsx` |
| 执行抽屉 | 新增 `ExecutionDrawer.tsx` + `AgentRound.tsx` + `ToolItem.tsx` + 异常状态展示 | `src/components/run/` |
| 页面布局 | 重构 `AgentRun.tsx` 支持三区域 Flexbox + StopButton 状态清理 | `src/views/AgentRun.tsx` |

### 后端

| 阶段 | 改造内容 | 关键文件 |
|------|---------|---------|
| **Phase 1 (V2.0)** | 前端通过 §7.1 映射表硬编码 16 个 nodeName → Round 归属。后端无需改动，当前 SSE 协议即可运行 | 无 |
| **Phase 2 (V3.0)** | SSEPayload 新增 `agentName`/`toolName`/`toolStatus`/`toolSummary` 字段；各节点 `format_sse()` 声明所属 Agent；Controller `_build_graph_response` 透传新字段；`graph.py` PlanExecutor 可能需要 emit per-tool 中间事件 | `app/workflows/node_base.py`, `app/api/streaming_graph_controller.py`, `app/workflows/nodes/*.py` |

---

## 9. 不变更项

- **会话列表 (ChatSessionSidebar)**: 保持现有布局和行为
- **AI 回复气泡 (AIBubble)**: 保持现有 Markdown/Report/Table 渲染逻辑
- **HumanFeedback**: 保持现有交互 (输入区替换为确认/拒绝按钮)
- **SSE 连接**: 保持现有 fetch + ReadableStream + 自动重连
- **多轮对话历史**: 保持现有 `sessionStateStore` 结构

---

## 10. 设计决策记录

| 决策 | 选项 | 选择 | 原因 |
|------|------|------|------|
| 布局方案 | A 三栏固定 / B 两栏+抽屉 / C 两栏+底部面板 | **B** | 默认简洁, 复杂任务自动展示面板 |
| 思考气泡模式 | 单例刷新 / 独立多气泡 / 折叠历史+高亮当前 | **单例刷新** | 心智模型简单, 减少对话区视觉噪音 |
| 抽屉生命周期 | 全自动 / 手动关闭 / 执行完置灰 | **手动关闭** | 用户掌控节奏, 不被自动消失打断 |
| 节点交互 | 展开tool / 定位气泡 / 弹出详情 / 无交互 | **三者全有** | 覆盖不同用户需求: 快速浏览 / 溯源 / 深挖细节 |
| 简单问题 (chitchat) | 不打开抽屉 | 是 | 闲聊场景无需展示执行过程 |
