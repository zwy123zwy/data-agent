# Frontend Interaction Design — 多 Agent 执行可视化

**日期**: 2026-05-18  
**状态**: DRAFT  
**关联**: `2026-05-18-multi-agent-architecture-design.md` (后端架构 V3.0)

---

## 1. 设计目标

将多 Agent 协作过程（Explorer → Analyst → Reporter）以「思考气泡 + 侧边执行面板」形式在前端可视化：

- **对话区**: 用户提问 → 🧠 思考气泡（单例，内容随 Agent 切换刷新）→ 🤖 AI 回复气泡
- **执行面板**: 右侧抽屉，执行开始时自动滑入，以 Round 为单位展示每个 Agent 的 tool 调用时序
- **参考**: 字节跳动 DataAgent 3.0 交互模式

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

| 当前阶段 | thinkingText |
|----------|-------------|
| KnowledgeRecall | 正在召回业务知识… |
| SchemaRecall | 正在探查数据表结构… |
| QueryRewrite | 正在改写查询… |
| TableRelation | 正在分析表关联关系… |
| Feasibility / Planner | 正在制定执行计划… |
| SqlGenerate | 正在生成 SQL 查询… |
| SqlExecute | 正在执行 SQL 查询… |
| SemanticConsistency | 正在校验语义一致性… |
| PythonGenerate | 正在生成分析代码… |
| PythonExecute | 正在执行 Python 分析… |
| PythonAnalyze | 正在解读分析结果… |
| ReportGenerator | 正在生成分析报告… |
| HumanFeedback | 等待人工确认… |

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

- **滑入**: `drawerVisible` 由 `KnowledgeRecall` 或 `SchemaRecall` 节点的首个 sse_output 触发 → `setDrawerVisible(true)`
- **关闭**: 仅用户点击 ✕ 按钮 → `setDrawerVisible(false)`
- **不自动关闭**: 执行结束后抽屉保持可见，内容置灰提示「执行完成」，下次执行重新点亮

### 面板内容 — AgentRound 分组规则

每个 **ReAct Agent 执行周期** 对应一个 Round：

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
| 失败 | `#ff4d4f` (红) | ✕ |
| 待执行 | `var(--border)` (灰) | ○ |
| 跳过 | `var(--text-secondary)` | — |

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
  status: 'pending' | 'running' | 'done' | 'error' | 'skipped'
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
  clearThinking: () => void

  // 重置
  reset: () => void
}

interface ThinkingState {
  text: string            // 主文案, "" = 隐藏
  hint: string            // 副文案 (如 "调用 get_schema → 获取到 5 张表")
  visible: boolean
}
```

### 用法: SSE 事件处理

```typescript
// handleSSEMessage 中的映射逻辑
switch (payload.nodeName) {
  case 'KnowledgeRecall':
    execStore.openDrawer()
    execStore.setThinking('正在召回业务知识…')
    execStore.upsertRound('Explorer', 1)
    break

  case 'SchemaRecall':
    execStore.setThinking('正在探查数据表结构…')
    execStore.addToolCall('Explorer', { name: 'get_schema', status: 'running' })
    break

  case 'QueryRewrite':
    execStore.addToolCall('Explorer', { name: 'rewrite_query', status: 'running' })
    break

  case 'TableRelation':
    execStore.addToolCall('Explorer', { name: 'find_relations', status: 'running' })
    // 标记 Explorer round 完成
    execStore.updateRoundStatus('Explorer', 'done')
    break

  case 'SqlGenerate':
    execStore.setThinking('正在生成 SQL 查询…')
    execStore.upsertRound('Analyst', 2)
    execStore.addToolCall('Analyst', { name: 'text_to_sql', status: 'running' })
    break

  case 'SqlExecute':
    execStore.addToolCall('Analyst', { name: 'execute_sql', status: 'running' })
    break

  case 'PythonGenerate':
    execStore.addToolCall('Analyst', { name: 'text_to_python', status: 'running' })
    break

  case 'PythonExecute':
    execStore.addToolCall('Analyst', { name: 'run_python', status: 'running' })
    break

  case 'ReportGenerator':
    execStore.setThinking('正在生成分析报告…')
    execStore.upsertRound('Reporter', 3)
    execStore.updateRoundStatus('Analyst', 'done')
    break

  // ... 每个 node 完成后更新对应 tool status 为 'done'
}

// 当后端返回 textType === 'tool_result' 时更新 tool 状态
if (payload.textType === 'tool_result') {
  execStore.updateToolCall(agentName, toolId, {
    status: 'done',
    summary: extractSummary(payload.text),
  })
}
```

---

## 7. SSE 事件 → UI 映射表

| 后端 nodeName | 思考气泡 | 执行面板 |
|--------------|---------|---------|
| IntentRecognition | — (内部判断) | — |
| (chitchat) | — | 不打开抽屉 |
| KnowledgeRecall | 🧠 正在召回业务知识… | 打开抽屉, +Round 1 Explorer |
| SchemaRecall | 🧠 正在探查数据表结构… | +tool: get_schema |
| QueryRewrite | 🧠 正在改写查询… | +tool: rewrite_query |
| TableRelation | 🧠 正在分析表关联关系… | +tool: find_relations |
| Feasibility | 🧠 正在制定执行计划… | — |
| Planner | 🧠 正在制定执行计划… | — |
| SqlGenerate | 🧠 正在生成 SQL 查询… | +Round 2 Analyst, +tool: text_to_sql |
| SemanticConsistency | 🧠 正在校验语义一致性… | +tool: semantic_check |
| SqlExecute | 🧠 正在执行 SQL 查询… | +tool: execute_sql |
| PythonGenerate | 🧠 正在生成分析代码… | +tool: text_to_python |
| PythonExecute | 🧠 正在执行 Python 分析… | +tool: run_python |
| PythonAnalyze | 🧠 正在解读分析结果… | +tool: analyze_result |
| ReportGenerator | 🧠 正在生成分析报告… | +Round 3 Reporter |
| HumanFeedback (interrupt) | ⏸️ 等待人工确认… | 抽屉暂停动画, 输入区出现确认/拒绝按钮 |
| END | 淡出消失 (AI 回复出现后 1s) | 抽屉保持, 执行状态置灰 |

### 需要后端适配的 SSE 字段

当前 SSE 协议输出 `nodeName` + `textType` + `text`。为支持执行面板精细化展示，建议在 SSE payload 中新增可选字段:

```json
{
  "nodeName": "SchemaRecall",
  "textType": "tool_call",
  "text": "正在获取数据表结构...",
  "agentName": "Explorer",        // NEW: 所属 Agent
  "toolName": "get_schema",       // NEW: 当前 tool 名称
  "toolStatus": "running",        // NEW: pending / running / done / error
  "toolSummary": "发现 5 张表"    // NEW: tool 结果摘要
}
```

> 这些字段为 **可选** — 前端 graceful degrade: 无这些字段时仅更新思考气泡，不展示 tool 细节。

---

## 8. 实现分工

| 层 | 负责 | 关键文件 |
|---|------|---------|
| 状态管理 | 新增 `executionStore` (Zustand) | `src/stores/executionStore.ts` |
| SSE 解析 | 在现有 `streamRequest.ts` 中增加映射逻辑 | `src/utils/streamRequest.ts` |
| 思考气泡 | 新增 `ThinkingBubble.tsx` | `src/components/run/ThinkingBubble.tsx` |
| 执行抽屉 | 新增 `ExecutionDrawer.tsx` + `AgentRound.tsx` + `ToolItem.tsx` | `src/components/run/` |
| 页面布局 | 重构 `AgentRun.tsx` 支持三区域 Flexbox | `src/views/AgentRun.tsx` |
| 后端 SSE | 可选: 在 `streaming_graph_controller.py` 的 sse_output 中增加 `agentName`/`toolName` 字段 | `app/api/streaming_graph_controller.py` |

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
