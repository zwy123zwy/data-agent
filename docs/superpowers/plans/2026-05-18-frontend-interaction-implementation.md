# 多 Agent 执行可视化 — 全栈实施文档

> **文档类型**: 全栈技术实施文档（前端 + 后端对齐）  
> **目标读者**: 前端工程师（React 19/TypeScript/Zustand/Ant Design）+ 后端工程师（FastAPI/LangGraph/Python）  
> **关联 Spec**: `docs/superpowers/specs/2026-05-18-frontend-interaction-design.md` §1–§10  
> **归档规则**: 实施过程中每完成一个 Task 提交一次，不必堆积多个 Task

---

## 架构总览

```
┌─────────────────────────────────────────────────────────────┐
│ 前端 (React 19 + Zustand 5 + Ant Design 5)                 │
│                                                             │
│  AgentRun.tsx ──重构──→ 三区域 Flexbox                       │
│    ├── ChatSessionSidebar (不变)                             │
│    ├── ChatArea                                             │
│    │   ├── ChatHeader + ExecutionToggleButton (新增)         │
│    │   ├── ChatMessages                                     │
│    │   │   ├── UserBubble (不变)                             │
│    │   │   ├── ThinkingBubble (★ 新增, 单例)                 │
│    │   │   └── AIBubble (不变)                               │
│    │   └── ChatInput + StopButton (改造)                     │
│    └── ExecutionDrawer (★ 新增, 360px 抽屉)                  │
│        └── AgentRoundList → AgentRound → ToolItem            │
│                                                             │
│  executionStore.ts (★ 新增 Zustand store)                    │
│  streamRequest.ts (改造: +nodeName switch → execStore)       │
├─────────────────────────────────────────────────────────────┤
│ HTTP SSE (text/event-stream)                                │
│   data: {agentId, threadId, nodeName, textType, text, ...}  │
│   event: complete / error / paused                          │
├─────────────────────────────────────────────────────────────┤
│ 后端 (FastAPI + LangGraph)                                  │
│                                                             │
│  Phase 1: 零改动 —— 当前 SSE 协议已满足 V2.0 前端需求        │
│  Phase 2: SSEPayload + format_sse() 声明 Agent/tool         │
│           _build_graph_response() 透传新字段                 │
│  Phase 3: V3.0 ReAct Agent 架构迁移                          │
│           (详见 2026-05-18-multi-agent-architecture-design)   │
└─────────────────────────────────────────────────────────────┘
```

---

## 文件变更清单

### 前端 (data-agent-fronted)

| 操作 | 文件 | 职责 |
|------|------|------|
| **Create** | `src/stores/executionStore.ts` | Zustand store: Round/Tool/Thinking 状态管理，stop/reset 生命周期 |
| **Create** | `src/components/run/ThinkingBubble.tsx` | 思考气泡单例组件，内容随 executionStore.thinkingText 刷新 |
| **Create** | `src/components/run/ExecutionDrawer.tsx` | 右侧抽屉容器，执行时滑入，用户手动关闭 |
| **Create** | `src/components/run/AgentRound.tsx` | 单个 Round 组件：RoundHeader + ToolList + RoundDetailPopover |
| **Create** | `src/components/run/ToolItem.tsx` | Tool 条目组件：图标 + 名称 + 状态指示 + 摘要 |
| **Modify** | `src/utils/streamRequest.ts` | SSE onMessage 中注入 nodeName→execStore 映射逻辑 |
| **Modify** | `src/views/AgentRun.tsx` | 布局从两栏改为三区域 Flexbox，集成 ExecutionDrawer |
| **Modify** | `src/types/graph.ts` | GraphNodeResponse 新增 4 个可选字段 (agentName 等) |

### 后端 (data-agent-backend) — Phase 2

| 操作 | 文件 | 职责 |
|------|------|------|
| **Modify** | `app/workflows/node_base.py` | SSEPayload 新增 agentName/toolName/toolStatus/toolSummary |
| **Modify** | `app/api/streaming_graph_controller.py` | _build_graph_response() 透传 4 个新字段 |
| **Modify** | `app/workflows/nodes/schema_recall.py` | format_sse() 添加 agentName="Explorer", toolName="get_schema" |
| **Modify** | `app/workflows/nodes/sql_generate.py` | format_sse() 添加 agentName="Analyst", toolName="text_to_sql" |
| **Modify** | `app/workflows/nodes/report_generator.py` | format_sse() 添加 agentName="Reporter" |
| **Modify** | 其余 6 个编排节点的 format_sse() | 按需声明 agentName (无 tool_name) |

---

# 第一部分: 前端实施 (Phase 1 — V2.0 即实施)

## 实施约定

- 每个 Step 包含具体代码，直接可用
- 组件使用 React 19 + TypeScript，inline styles（与现有代码一致）
- Zustand 5.x `create()` 模式: `create<Type>()((set, get) => ({}))`
- Ant Design 5.x 组件: `Drawer`, `Popover`, `Tag`, `Progress`
- 无需测试框架（项目当前无测试基础设施，Phase 1 手动验证）

---

### Task 1: GraphNodeResponse 类型扩展

**文件:**
- Modify: `src/types/graph.ts`

**说明**: 为 SSE payload 预留 V3.0 字段，当前 Phase 1 前端通过 nodeName infer 值，Phase 2 后端直接发送这些字段。

- [ ] **Step 1: 扩展 GraphNodeResponse 接口**

```typescript
// src/types/graph.ts

export type TextType = 'JSON' | 'PYTHON' | 'SQL' | 'HTML' | 'MARK_DOWN' | 'RESULT_SET' | 'TEXT';

export interface GraphRequest {
  agentId: number;
  threadId?: string;
  query: string;
  humanFeedback: boolean;
  humanFeedbackContent?: string;
  rejectedPlan: boolean;
  nl2sqlOnly: boolean;
}

export interface GraphNodeResponse {
  agentId: string;
  threadId: string;
  nodeName: string;
  textType: TextType;
  text: string;
  error: boolean;
  complete: boolean;
  // V3.0 可选字段 (Phase 1 通过 nodeName 降级推断, Phase 2 后端直接发送)
  agentName?: string;   // Explorer | Analyst | Reporter
  toolName?: string;    // get_schema | execute_sql | ...
  toolStatus?: 'pending' | 'running' | 'done' | 'error';
  toolSummary?: string; // 单行摘要, < 80 字符
}
```

- [ ] **Step 2: Type-check 验证**

```bash
cd C:/Users/Zhangwenye/Desktop/data-analysis-agent/data-agent-fronted
npm run type-check
```

预期: 无新增错误（可选字段不影响现有代码）。

- [ ] **Step 3: Commit**

```bash
git add src/types/graph.ts
git commit -m "feat: add V3.0 optional fields to GraphNodeResponse type"
```

---

### Task 2: executionStore (Zustand)

**文件:**
- Create: `src/stores/executionStore.ts`

**说明**: 独立于 `sessionStateStore` 的新 store，管理执行面板和思考气泡的全部状态。接口定义来自 spec §6。

- [ ] **Step 1: 创建 store 文件**

```typescript
// src/stores/executionStore.ts
import { create } from 'zustand';

// ---- 类型 ----

export type ToolStatus = 'pending' | 'running' | 'done' | 'error' | 'skipped';
export type RoundStatus = 'pending' | 'running' | 'done' | 'partial_failure' | 'error' | 'skipped';
export type AgentName = 'Explorer' | 'Analyst' | 'Reporter';

export interface ToolCall {
  id: string;
  name: string;
  status: ToolStatus;
  summary?: string;
  output?: unknown;
  startedAt?: number;
  finishedAt?: number;
}

export interface AgentRound {
  id: string;
  agentName: AgentName;
  roundIndex: number;
  status: RoundStatus;
  tools: ToolCall[];
  input?: string;
  output?: string;
}

interface ExecutionState {
  // 抽屉
  drawerVisible: boolean;
  openDrawer: () => void;
  closeDrawer: () => void;

  // Round 管理
  rounds: AgentRound[];
  activeRoundIndex: number;
  upsertRound: (agentName: AgentName, roundIndex: number) => AgentRound;
  updateRoundStatus: (agentName: AgentName, status: RoundStatus) => void;
  addToolCall: (agentName: AgentName, tool: ToolCall) => void;
  updateToolCall: (agentName: AgentName, toolId: string, update: Partial<ToolCall>) => void;

  // 思考气泡
  thinkingText: string;
  thinkingHint: string;
  setThinking: (text: string, hint?: string) => void;
  setThinkingHint: (hint: string) => void;
  clearThinking: () => void;

  // Tool 完成追踪
  lastAgentName: AgentName | null;
  finishLastToolCall: (agentName: AgentName) => void;
  updateLastRunningToolStatus: (status: ToolStatus) => void;
  updateLastRunningRoundStatus: (status: RoundStatus) => void;

  // 生命周期
  stop: () => void;
  reset: () => void;
}

// ---- 工具函数 ----

let _toolIdCounter = 0;
function nextToolId(): string {
  _toolIdCounter += 1;
  return `tool_${_toolIdCounter}`;
}

let _roundIdCounter = 0;
function nextRoundId(): string {
  _roundIdCounter += 1;
  return `round_${_roundIdCounter}`;
}

// ---- Store ----

export const useExecutionStore = create<ExecutionState>()((set, get) => ({
  drawerVisible: false,
  openDrawer: () => set({ drawerVisible: true }),
  closeDrawer: () => set({ drawerVisible: false }),

  rounds: [],
  activeRoundIndex: -1,

  upsertRound: (agentName, roundIndex) => {
    const existing = get().rounds.find((r) => r.agentName === agentName);
    if (existing) {
      set({ activeRoundIndex: existing.roundIndex });
      return existing;
    }
    const round: AgentRound = {
      id: nextRoundId(),
      agentName,
      roundIndex,
      status: 'running',
      tools: [],
    };
    set((s) => ({
      rounds: [...s.rounds, round],
      activeRoundIndex: roundIndex,
      lastAgentName: agentName,
    }));
    return round;
  },

  updateRoundStatus: (agentName, status) => {
    set((s) => ({
      rounds: s.rounds.map((r) =>
        r.agentName === agentName ? { ...r, status } : r,
      ),
    }));
  },

  // 添加 tool 时自动完成同 Round 内上一 running tool
  // 理由: V2.0 线性流水线中一个节点对应一个 tool, 新 tool 开始即上一 tool 完成
  // data.complete 在 SSE data 消息中永远为 false (仅 event:complete 中为 true),
  // 故 handleNodeForExecution 中的 complete 判断不可用, 在此处自动完成
  addToolCall: (agentName, tool) => {
    set((s) => ({
      rounds: s.rounds.map((r) => {
        if (r.agentName !== agentName) return r;
        // 自动完成上一 running tool
        const completedTools = r.tools.map((t) =>
          t.status === 'running' ? { ...t, status: 'done' as const, finishedAt: Date.now() } : t,
        );
        return {
          ...r,
          tools: [...completedTools, { ...tool, id: tool.id || nextToolId(), startedAt: Date.now() }],
        };
      }),
      lastAgentName: agentName,
    }));
  },

  updateToolCall: (agentName, toolId, update) => {
    set((s) => ({
      rounds: s.rounds.map((r) =>
        r.agentName === agentName
          ? {
              ...r,
              tools: r.tools.map((t) =>
                t.id === toolId ? { ...t, ...update, finishedAt: update.status === 'done' || update.status === 'error' ? Date.now() : t.finishedAt } : t,
              ),
            }
          : r,
      ),
    }));
  },

  thinkingText: '',
  thinkingHint: '',

  setThinking: (text, hint) => set({ thinkingText: text, thinkingHint: hint || '' }),
  setThinkingHint: (hint) => set({ thinkingHint: hint }),
  clearThinking: () => set({ thinkingText: '', thinkingHint: '' }),

  lastAgentName: null,

  finishLastToolCall: (agentName) => {
    set((s) => ({
      rounds: s.rounds.map((r) => {
        if (r.agentName !== agentName) return r;
        const tools = [...r.tools];
        // 找到最后一个 running 的 tool, 标记为 done
        for (let i = tools.length - 1; i >= 0; i--) {
          if (tools[i].status === 'running') {
            tools[i] = { ...tools[i], status: 'done', finishedAt: Date.now() };
            break;
          }
        }
        return { ...r, tools };
      }),
    }));
  },

  updateLastRunningToolStatus: (status) => {
    set((s) => ({
      rounds: s.rounds.map((r) => ({
        ...r,
        tools: r.tools.map((t) =>
          t.status === 'running' ? { ...t, status, finishedAt: Date.now() } : t,
        ),
      })),
    }));
  },

  updateLastRunningRoundStatus: (status) => {
    set((s) => ({
      rounds: s.rounds.map((r) =>
        r.status === 'running' ? { ...r, status } : r,
      ),
    }));
  },

  stop: () => {
    set((s) => ({
      rounds: s.rounds.map((round) => ({
        ...round,
        status: round.status === 'running' ? 'skipped' : round.status,
        tools: round.tools.map((tool) => ({
          ...tool,
          status: tool.status === 'running' ? 'skipped' : tool.status,
        })),
      })),
      thinkingText: '',
      thinkingHint: '',
    }));
  },

  reset: () => {
    _toolIdCounter = 0;
    _roundIdCounter = 0;
    set({
      drawerVisible: false,
      rounds: [],
      activeRoundIndex: -1,
      thinkingText: '',
      thinkingHint: '',
      lastAgentName: null,
    });
  },
}));
```

- [ ] **Step 2: Type-check 验证**

```bash
npm run type-check
```

- [ ] **Step 3: Commit**

```bash
git add src/stores/executionStore.ts
git commit -m "feat: add executionStore — Zustand store for rounds, tools, and thinking bubble"
```

---

### Task 3: SSE 映射层 — streamRequest.ts 改造

**文件:**
- Modify: `src/utils/streamRequest.ts`

**说明**: 在现有 `onMessage` 回调中注入调用 `executionStore` 的逻辑。**不修改现有 nodeBlocks 逻辑**，在现有代码之前插入 `handleNodeForExecution` 调用。

- [ ] **Step 1: 添加 import 和 NODE_TO_EXECUTION 映射**

```typescript
// 在 streamRequest.ts 顶部添加:
import { useExecutionStore } from '../stores/executionStore';
import type { AgentName } from '../stores/executionStore';

// ---- 节点名 → Agent Round + Tool 映射 (spec §7.1) ----

interface NodeExecutionMapping {
  agentName?: AgentName;
  roundIndex?: number;
  toolName?: string;
  thinkingText: string;
  openDrawer?: boolean;
  finishRound?: AgentName;
}

const NODE_TO_EXECUTION: Record<string, NodeExecutionMapping> = {
  EvidenceRecallNode: {
    agentName: 'Explorer', roundIndex: 1, toolName: 'search_knowledge',
    thinkingText: '正在召回业务知识…', openDrawer: true,
  },
  QueryEnhanceNode: {
    agentName: 'Explorer', roundIndex: undefined, toolName: 'rewrite_query',
    thinkingText: '正在改写查询…',
  },
  SchemaRecallNode: {
    agentName: 'Explorer', roundIndex: undefined, toolName: 'get_schema',
    thinkingText: '正在探查数据表结构…',
  },
  TableRelationNode: {
    agentName: 'Explorer', roundIndex: undefined, toolName: 'find_relations',
    thinkingText: '正在分析表关联关系…',
  },
  FeasibilityAssessmentNode: {
    thinkingText: '正在制定执行计划…',
  },
  PlannerNode: {
    thinkingText: '正在制定执行计划…', finishRound: 'Explorer',
  },
  PlanExecutorNode: {
    thinkingText: '正在执行步骤…', // plan_executor 产生可见输出, 与 nodeBlocks 保持一致
  },
  SqlGenerateNode: {
    agentName: 'Analyst', roundIndex: 2, toolName: 'text_to_sql',
    thinkingText: '正在生成 SQL 查询…',
  },
  SemanticConsistencyNode: {
    agentName: 'Analyst', roundIndex: undefined, toolName: 'semantic_check',
    thinkingText: '正在校验语义一致性…',
  },
  SqlExecuteNode: {
    agentName: 'Analyst', roundIndex: undefined, toolName: 'execute_sql',
    thinkingText: '正在执行 SQL 查询…',
  },
  PythonGenerateNode: {
    agentName: 'Analyst', roundIndex: undefined, toolName: 'text_to_python',
    thinkingText: '正在生成分析代码…',
  },
  PythonExecuteNode: {
    agentName: 'Analyst', roundIndex: undefined, toolName: 'run_python',
    thinkingText: '正在执行 Python 分析…',
  },
  PythonAnalyzeNode: {
    agentName: 'Analyst', roundIndex: undefined, toolName: 'analyze_result',
    thinkingText: '正在解读分析结果…',
  },
  ReportGeneratorNode: {
    agentName: 'Reporter', roundIndex: 3,
    thinkingText: '正在生成分析报告…', finishRound: 'Analyst',
  },
  HumanFeedbackNode: {
    thinkingText: '等待人工确认…',
  },
  IntentRecognitionNode: {
    thinkingText: '', // 内部判断，不展示
  },
  ChitchatNode: {
    thinkingText: '', // 闲聊回复，不展示执行面板
  },
};

/** 将 SSE nodeName 事件翻译为 executionStore 调用 */
function handleNodeForExecution(nodeName: string, data: { text: string; textType: string; complete: boolean }) {
  const mapping = NODE_TO_EXECUTION[nodeName];
  if (!mapping) return;

  const execStore = useExecutionStore.getState();

  // 1. 打开抽屉 (首个可见节点)
  if (mapping.openDrawer) {
    execStore.openDrawer();
  }

  // 2. 思考气泡
  if (mapping.thinkingText) {
    execStore.setThinking(mapping.thinkingText);

    // 提取副文案: TEXT 类型从 text 首行截取, SQL/PYTHON/RESULT_SET 使用 tool 名
    if (!data.complete && data.text) {
      if (data.textType === 'TEXT') {
        execStore.setThinkingHint(truncateText(data.text, 80));
      } else if (mapping.toolName && ['SQL', 'PYTHON', 'RESULT_SET'].includes(data.textType)) {
        execStore.setThinkingHint(`${mapping.toolName} 输出中…`);
      }
    }
  }

  // 3. Round/Tool
  if (mapping.agentName && mapping.roundIndex) {
    execStore.upsertRound(mapping.agentName, mapping.roundIndex);
  }
  if (mapping.agentName && mapping.toolName) {
    execStore.addToolCall(mapping.agentName, {
      id: '',
      name: mapping.toolName,
      status: 'running',
    });
  }

  // 4. Round 完成
  if (mapping.finishRound) {
    execStore.updateRoundStatus(mapping.finishRound, 'done');
  }

  // 5. 节点完成 → tool 完成由 addToolCall 自动处理 (见 store 注释)
}

function truncateText(text: string, maxLen: number = 80): string {
  const firstLine = text.split('\n')[0].trim();
  return firstLine.length > maxLen
    ? firstLine.slice(0, maxLen) + '...'
    : firstLine;
}
```

- [ ] **Step 2: 在 sendGraphRequest → onMessage 中注入调用**

在 `onMessage: async (data: GraphNodeResponse) => {` 函数的**最开头**（`if (data.error)` 检查之后），插入一行：

```typescript
// 在 sendGraphRequest 的 onMessage 中, if (data.error) return 之后, 现有 nodeBlocks 逻辑之前:
      // ★ 执行面板 + 思考气泡映射
      handleNodeForExecution(data.nodeName, {
        text: data.text,
        textType: data.textType,
        complete: data.complete,
      });
```

- [ ] **Step 3: 在 onComplete / onError / onPaused 中注入生命周期处理**

**onComplete** (在现有 `setState(sid, { isStreaming: false, closeStream: null })` 之后添加):

```typescript
      // 标记最后 Agent round 为 done (Reporter round 由此完成)
      const es = useExecutionStore.getState();
      if (es.lastAgentName) {
        es.updateRoundStatus(es.lastAgentName, 'done');
      }
      // 思考气泡在 1s 后淡出
      setTimeout(() => {
        useExecutionStore.getState().clearThinking();
      }, 1000);
```

**onError** (在现有 `setState(sid, { isStreaming: false, closeStream: null })` 之后添加):

```typescript
      const execStore = useExecutionStore.getState();
      execStore.updateLastRunningToolStatus('error');
      execStore.updateLastRunningRoundStatus('error');
      execStore.clearThinking();
```

**onPaused** (在现有逻辑之后添加):

```typescript
      // 抽屉和思考气泡保持当前状态, pause 不改变任何 executionStore 状态
```

- [ ] **Step 4: Type-check 验证**

```bash
npm run type-check
```

- [ ] **Step 5: Commit**

```bash
git add src/utils/streamRequest.ts
git commit -m "feat: wire SSE nodeName → executionStore mapping in streamRequest.ts"
```

---

### Task 4: ThinkingBubble 组件

**文件:**
- Create: `src/components/run/ThinkingBubble.tsx`

**说明**: 单例思考气泡，从 `executionStore.thinkingText` 读取当前文案。空字符串时不渲染。

- [ ] **Step 1: 创建组件**

```typescript
// src/components/run/ThinkingBubble.tsx
import React from 'react';
import { useExecutionStore } from '../../stores/executionStore';

/**
 * ThinkingBubble — 思考气泡 (单例模式)
 *
 * 行为: thinkingText 非空时渲染一个左对齐灰色气泡,
 *       内容随 executionStore.thinkingText 实时刷新,
 *       thinkingHint 显示为副文案.
 */
const ThinkingBubble: React.FC = () => {
  const thinkingText = useExecutionStore((s) => s.thinkingText);
  const thinkingHint = useExecutionStore((s) => s.thinkingHint);

  if (!thinkingText) return null;

  return (
    <div style={{ display: 'flex', justifyContent: 'flex-start', marginBottom: 16 }} data-thinking-bubble>
      <div
        style={{
          maxWidth: '85%',
          background: 'var(--bg-secondary, #f0f2f5)',
          border: '1px solid var(--border, #e8e8e8)',
          borderRadius: 12,
          padding: '10px 14px',
          fontSize: 13,
        }}
      >
        <div style={{ color: '#1677ff', marginBottom: thinkingHint ? 4 : 0, fontWeight: 500 }}>
          🧠 {thinkingText}
        </div>
        {thinkingHint && (
          <div style={{ color: '#8c8c8c', fontSize: 12 }}>{thinkingHint}</div>
        )}
      </div>
    </div>
  );
};

export default ThinkingBubble;
```

- [ ] **Step 2: Type-check 验证**

```bash
npm run type-check
```

- [ ] **Step 3: Commit**

```bash
git add src/components/run/ThinkingBubble.tsx
git commit -m "feat: add ThinkingBubble component — singleton, driven by executionStore"
```

---

### Task 5: ToolItem 组件

**文件:**
- Create: `src/components/run/ToolItem.tsx`

- [ ] **Step 1: 创建组件**

```typescript
// src/components/run/ToolItem.tsx
import React from 'react';
import {
  CheckCircleFilled,
  CloseCircleFilled,
  LoadingOutlined,
  MinusCircleOutlined,
  ClockCircleOutlined,
} from '@ant-design/icons';
import type { ToolCall } from '../../stores/executionStore';

interface Props {
  tool: ToolCall;
  onClick?: () => void; // 点击 → 对话区滚动定位
}

const TOOL_ICON: Record<string, string> = {
  search_knowledge: '📚',
  get_schema: '🔍',
  rewrite_query: '✏️',
  find_relations: '🔗',
  text_to_sql: '📝',
  semantic_check: '✅',
  execute_sql: '⚡',
  text_to_python: '🐍',
  run_python: '▶️',
  analyze_result: '📊',
};

const STATUS_ICON: Record<string, React.ReactNode> = {
  done: <CheckCircleFilled style={{ color: '#52c41a', fontSize: 12 }} />,
  running: <LoadingOutlined spin style={{ color: '#1677ff', fontSize: 12 }} />,
  error: <CloseCircleFilled style={{ color: '#ff4d4f', fontSize: 12 }} />,
  pending: <ClockCircleOutlined style={{ color: '#d9d9d9', fontSize: 12 }} />,
  skipped: <MinusCircleOutlined style={{ color: '#8c8c8c', fontSize: 12 }} />,
};

const ToolItem: React.FC<Props> = ({ tool, onClick }) => {
  const icon = TOOL_ICON[tool.name] || '🔧';

  return (
    <div
      onClick={onClick}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        padding: '4px 8px',
        fontSize: 12,
        color: tool.status === 'running' ? '#1677ff' : '#595959',
        cursor: onClick ? 'pointer' : 'default',
        borderRadius: 4,
        transition: 'background 0.15s',
      }}
      onMouseEnter={(e) => { if (onClick) (e.currentTarget as HTMLElement).style.background = '#f5f5f5'; }}
      onMouseLeave={(e) => { if (onClick) (e.currentTarget as HTMLElement).style.background = 'transparent'; }}
    >
      <span>{icon}</span>
      <span style={{ flex: 1, fontWeight: tool.status === 'running' ? 500 : 400 }}>
        {tool.name}
      </span>
      {tool.summary && tool.status === 'done' && (
        <span style={{ color: '#8c8c8c', fontSize: 11, maxWidth: 120, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {tool.summary}
        </span>
      )}
      {tool.summary && tool.status === 'error' && (
        <span style={{ color: '#ff4d4f', fontSize: 11, maxWidth: 120, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {tool.summary}
        </span>
      )}
      {STATUS_ICON[tool.status] || null}
    </div>
  );
};

export default ToolItem;
```

- [ ] **Step 2: Type-check 验证**

```bash
npm run type-check
```

- [ ] **Step 3: Commit**

```bash
git add src/components/run/ToolItem.tsx
git commit -m "feat: add ToolItem component — icon + name + status indicator"
```

---

### Task 6: AgentRound 组件

**文件:**
- Create: `src/components/run/AgentRound.tsx`

- [ ] **Step 1: 创建组件**

```typescript
// src/components/run/AgentRound.tsx
import React, { useState } from 'react';
import { Popover, Tag } from 'antd';
import {
  CaretDownOutlined,
  CaretRightOutlined,
  InfoCircleOutlined,
} from '@ant-design/icons';
import type { AgentRound as AgentRoundType } from '../../stores/executionStore';
import ToolItem from './ToolItem';

interface Props {
  round: AgentRoundType;
  isActive: boolean;
  onToggle: () => void;
  onToolClick?: (toolId: string) => void;
}

const ROUND_LABEL: Record<string, string> = {
  Explorer: '探查数据',
  Analyst: '分析与执行',
  Reporter: '生成报告',
};

const STATUS_CONFIG: Record<string, { color: string; icon: string }> = {
  done: { color: '#52c41a', icon: '✓' },
  running: { color: '#1677ff', icon: '⟳' },
  partial_failure: { color: '#faad14', icon: '⚠' },
  error: { color: '#ff4d4f', icon: '✕' },
  pending: { color: '#d9d9d9', icon: '○' },
  skipped: { color: '#8c8c8c', icon: '—' },
};

const AgentRoundComponent: React.FC<Props> = ({ round, isActive, onToggle, onToolClick }) => {
  const [popoverOpen, setPopoverOpen] = useState(false);
  const config = STATUS_CONFIG[round.status] || STATUS_CONFIG.pending;
  const label = ROUND_LABEL[round.agentName] || round.agentName;

  return (
    <div
      style={{
        border: `1px solid ${isActive ? '#1677ff' : '#e8e8e8'}`,
        borderRadius: 8,
        overflow: 'hidden',
        marginBottom: 12,
        transition: 'border-color 0.2s',
      }}
    >
      {/* RoundHeader */}
      <div
        onClick={onToggle}
        style={{
          padding: '8px 12px',
          background: isActive ? '#e6f4ff' : '#fafafa',
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          cursor: 'pointer',
          userSelect: 'none',
          fontSize: 13,
          fontWeight: 600,
        }}
      >
        <span style={{ color: config.color }}>{config.icon}</span>
        <span style={{ color: isActive ? '#1677ff' : '#303133' }}>
          Round {round.roundIndex} · {label}
        </span>
        {round.status === 'running' && (
          <Tag color="processing" style={{ marginLeft: 4, fontSize: 11, lineHeight: '18px' }}>执行中</Tag>
        )}
        {round.status === 'done' && (
          <Tag color="success" style={{ marginLeft: 4, fontSize: 11, lineHeight: '18px' }}>完成</Tag>
        )}
        <span style={{ flex: 1 }} />
        <Popover
          open={popoverOpen}
          onOpenChange={setPopoverOpen}
          trigger="click"
          placement="left"
          title={`${label} 详情`}
          content={
            <div style={{ maxWidth: 360, fontSize: 12 }}>
              {round.input && (
                <div style={{ marginBottom: 8 }}>
                  <strong>输入:</strong>
                  <pre style={{ margin: '4px 0', whiteSpace: 'pre-wrap', wordBreak: 'break-word', background: '#f5f5f5', padding: 8, borderRadius: 4 }}>
                    {round.input.slice(0, 500)}
                  </pre>
                </div>
              )}
              {round.output && (
                <div style={{ marginBottom: 8 }}>
                  <strong>输出:</strong>
                  <pre style={{ margin: '4px 0', whiteSpace: 'pre-wrap', wordBreak: 'break-word', background: '#f5f5f5', padding: 8, borderRadius: 4 }}>
                    {round.output.slice(0, 500)}
                  </pre>
                </div>
              )}
              <div>
                <strong>Tool 调用:</strong>
                {round.tools.length === 0 && <div style={{ color: '#8c8c8c' }}>无</div>}
                {round.tools.map((t) => (
                  <div key={t.id} style={{ margin: '2px 0' }}>
                    {t.name} — {t.status}
                    {t.finishedAt && t.startedAt && (
                      <span style={{ color: '#8c8c8c' }}> ({t.finishedAt - t.startedAt}ms)</span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          }
        >
          <InfoCircleOutlined
            onClick={(e) => { e.stopPropagation(); setPopoverOpen(true); }}
            style={{ fontSize: 14, color: '#bfbfbf', cursor: 'pointer' }}
          />
        </Popover>
        {onToggle && (
          isActive ? <CaretDownOutlined style={{ fontSize: 12, color: '#bfbfbf' }} />
            : <CaretRightOutlined style={{ fontSize: 12, color: '#bfbfbf' }} />
        )}
      </div>

      {/* ToolList — 展开时显示 */}
      {isActive && (
        <div
          style={{
            padding: '4px 8px',
            animation: 'max-height 0.2s ease',
          }}
        >
          {round.tools.length === 0 && (
            <div style={{ color: '#8c8c8c', fontSize: 12, padding: '4px 8px' }}>等待中…</div>
          )}
          {round.tools.map((tool) => (
            <ToolItem
              key={tool.id}
              tool={tool}
              onClick={onToolClick ? () => onToolClick(tool.id) : undefined}
            />
          ))}
        </div>
      )}
    </div>
  );
};

export default AgentRoundComponent;
```

- [ ] **Step 2: Type-check 验证**

```bash
npm run type-check
```

- [ ] **Step 3: Commit**

```bash
git add src/components/run/AgentRound.tsx
git commit -m "feat: add AgentRound component — collapsible round with tools + popover"
```

---

### Task 7: ExecutionDrawer 组件

**文件:**
- Create: `src/components/run/ExecutionDrawer.tsx`

- [ ] **Step 1: 创建组件**

```typescript
// src/components/run/ExecutionDrawer.tsx
import React, { useState } from 'react';
import { Button } from 'antd';
import { CloseOutlined } from '@ant-design/icons';
import { useExecutionStore } from '../../stores/executionStore';
import AgentRoundComponent from './AgentRound';

/**
 * ExecutionDrawer — 右侧执行面板
 *
 * 生命周期:
 *   - 执行开始时从右侧滑入 (transform: translateX + transition 0.3s)
 *   - 用户点击 ✕ 手动关闭
 *   - 全部 Round 完成时顶部显示 "✓ 执行完成" 提示
 */
const ExecutionDrawer: React.FC = () => {
  const drawerVisible = useExecutionStore((s) => s.drawerVisible);
  const rounds = useExecutionStore((s) => s.rounds);
  const closeDrawer = useExecutionStore((s) => s.closeDrawer);

  // 手风琴: 同一时间只展开一个 Round
  // 初始 undefined 使首次渲染时自动展开执行中的 Round (null 则跳过自动展开)
  const [expandedRoundId, setExpandedRoundId] = useState<string | undefined>(undefined);

  // 默认展开执行中的 Round
  const activeRoundId = rounds.find((r) => r.status === 'running')?.id;
  // 用户手动词切换后 expandedRoundId 为 null (已手动关闭), 不为 undefined (自动模式)
  const currentExpanded = expandedRoundId !== undefined ? expandedRoundId : activeRoundId;

  const allDone = rounds.length > 0 && rounds.every((r) => r.status === 'done');

  const handleToggle = (roundId: string) => {
    setExpandedRoundId((prev) => (prev === roundId ? null : roundId));
  };

  // 点击 tool → 对话区滚动定位
  const handleToolClick = (_toolId: string) => {
    // 触发 ChatMessages 滚动到思考气泡位置
    const chatContainer = document.querySelector('.chat-container');
    if (chatContainer) {
      const thinkingBubble = chatContainer.querySelector('[data-thinking-bubble]');
      if (thinkingBubble) {
        thinkingBubble.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }
  };

  return (
    <div
      style={{
        width: drawerVisible ? 360 : 0,
        minWidth: drawerVisible ? 360 : 0,
        borderLeft: drawerVisible ? '1px solid #e8e8e8' : 'none',
        display: 'flex',
        flexDirection: 'column',
        background: '#fff',
        overflow: 'hidden',
        transition: 'width 0.3s ease, min-width 0.3s ease',
        height: '100%',
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: '12px 16px',
          borderBottom: '1px solid #e8e8e8',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          fontWeight: 600,
          fontSize: 14,
          flexShrink: 0,
        }}
      >
        <span>⚙️ 执行过程</span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {rounds.length > 0 && (
            <span style={{ fontSize: 11, color: '#8c8c8c', fontWeight: 400 }}>
              Round {rounds.filter((r) => r.status === 'done').length}/{rounds.length}
            </span>
          )}
          <Button
            type="text"
            size="small"
            icon={<CloseOutlined />}
            onClick={closeDrawer}
          />
        </div>
      </div>

      {/* 执行完成提示 */}
      {allDone && (
        <div
          style={{
            padding: '6px 0',
            textAlign: 'center',
            fontSize: 12,
            color: '#8c8c8c',
            borderBottom: '1px solid #f0f0f0',
            flexShrink: 0,
          }}
        >
          ✓ 执行完成
        </div>
      )}

      {/* Round 列表 */}
      <div style={{ flex: 1, overflowY: 'auto', padding: 12 }}>
        {rounds.length === 0 && (
          <div style={{ color: '#8c8c8c', fontSize: 13, textAlign: 'center', padding: 40 }}>
            等待执行…
          </div>
        )}
        {rounds.map((round) => (
          <AgentRoundComponent
            key={round.id}
            round={round}
            isActive={currentExpanded === round.id || round.status === 'running'}
            onToggle={() => handleToggle(round.id)}
            onToolClick={handleToolClick}
          />
        ))}
      </div>
    </div>
  );
};

export default ExecutionDrawer;
```

- [ ] **Step 2: Type-check 验证**

```bash
npm run type-check
```

- [ ] **Step 3: Commit**

```bash
git add src/components/run/ExecutionDrawer.tsx
git commit -m "feat: add ExecutionDrawer — slide-in panel with round/tool list"
```

---

### Task 8: AgentRun.tsx 布局重构

**文件:**
- Modify: `src/views/AgentRun.tsx`

**说明**: 将现有两栏布局（Sidebar + ChatArea）改为三区域 Flexbox（Sidebar + ChatArea + ExecutionDrawer）。在 ChatHeader 注入 ExecutionToggleButton。在 ChatMessages 区域注入 ThinkingBubble 渲染。Stop 按钮连接 executionStore.stop()。

当前 AgentRun.tsx 结构:
```
<div display:flex>           ← 最外层
  <ChatSessionSidebar />     ← 左侧
  <main flex:1>              ← 右侧主区域
    消息列表 (ChatMessages)
    HumanFeedback
    输入区 (ChatInput)
  </main>
</div>
```

目标结构:
```
<div display:flex>           ← 最外层，高度 calc(100vh - 56px)
  <ChatSessionSidebar />     ← 左侧 (不变)
  <main flex:1>              ← 中间主区域
    <ChatHeader />           ← ★ 新增: 标题行 + 执行按钮
    消息列表 (ChatMessages + ThinkingBubble)
    HumanFeedback
    输入区 (ChatInput)
  </main>
  <ExecutionDrawer />        ← ★ 新增: 右侧抽屉
</div>
```

- [ ] **Step 1: 添加 import**

在 `AgentRun.tsx` 顶部添加:

```typescript
import ExecutionDrawer from '../components/run/ExecutionDrawer';
import ThinkingBubble from '../components/run/ThinkingBubble';
import { useExecutionStore } from '../stores/executionStore';
```

- [ ] **Step 2: 读取 executionStore**

在 `const AgentRun: React.FC = () => {` 函数体内，`const chat = useAgentChat(agentId);` 之后添加:

```typescript
  // 执行面板状态
  const executionStore = useExecutionStore();
```

- [ ] **Step 3: 修改 handleStop 连接 executionStore.stop()**

在 `useAgentChat.ts` 的 `handleStop` 不会变，但 AgentRun 中需要确保停止时调用。找到 `chat.handleStop` 的调用位置，确保调用链中包含:

```typescript
// handleStop 实际已在 useAgentChat 中定义, 但需要扩展为:
// 在 useAgentChat.ts 的 handleStop 中（或通过包装）调用:
// useExecutionStore.getState().stop();
```

由于 handleStop 在 useAgentChat hook 内部，最简单的方式是在 `streamRequest.ts` 的 `onError` 和 `onStop`(返回的 cancel 函数) 中已处理。另外需要在 `sendGraphRequest` 返回的 cancel 函数被调用时触发 stop——这个 cancel 函数在 useAgentChat 的 `handleStop` 中通过 `closeStream` 调用。在 `streamRequest.ts` 中 `onError` 已处理，但主动 stop 路径需要补充。

在 `sendGraphRequest` 的 `return () => { ... }` (即 cancel 函数) 中添加:

```typescript
// 在 streamRequest.ts sendGraphRequest 的 return 语句中 (closeStream 调用处):
// streamSearch 已返回 cancel 函数，在 sendGraphRequest 返回的 cleanup 中:
// 实际主动停止由 onError 的 AbortError 路径处理，但额外保险:
// 在 sendGraphRequest 的 onStop 相关路径被触发时, 已经在 useAgentChat.handleStop 中
// 通过 closeStream() 触发 cleanup, 此时需要调用:
```

**简化方案**: 在 `AgentRun.tsx` 中包装 `handleStop`:

找到这段代码 (约在 StopButton onClick 处):
```tsx
onClick={chat.handleStop}
```

改为:
```tsx
onClick={() => {
  useExecutionStore.getState().stop();
  chat.handleStop();
}}
```

- [ ] **Step 4: 在 ChatMessages 调用上方嵌入 ThinkingBubble**

在 `AgentRun.tsx` 的消息列表 `<div>` 内部，`<ChatMessages>` 组件**前面**插入 `<ThinkingBubble>`:

找到:
```tsx
<ChatMessages
  currentSessionId={chat.currentSessionId}
  ...
/>
```

在 `<ChatMessages>` 之前添加:
```tsx
            <ThinkingBubble />
```

> `data-thinking-bubble` 属性已在 Task 4 ThinkingBubble 组件中内置，ToolItem 点击可定位。
> **注意**: Task 8 commit 中无需再包含 ThinkingBubble.tsx 的修补。

- [ ] **Step 5: 添加 ExecutionToggleButton**

在消息列表上方、`ChatHeader` 位置（目前 AgentRun 没有独立 Header，标题信息在 ChatMessages 中通过 ChatSessionSidebar 处理）。简化方案：在消息列表 `<div>` 的开头添加:

```tsx
{/* 执行面板切换按钮 (抽屉关闭时可见) */}
{!executionStore.drawerVisible && (
  <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 8 }}>
    <Button
      size="small"
      icon={<ControlOutlined />}
      onClick={() => executionStore.openDrawer()}
    >
      执行过程 ▸
    </Button>
  </div>
)}
```

需要在 import 中添加 `ControlOutlined`:
```typescript
import { ..., ControlOutlined } from '@ant-design/icons';
```

- [ ] **Step 6: 在最外层 div 中添加 ExecutionDrawer**

在 `</main>` 和 `</div>` (最外层) 之间插入:

```tsx
      {/* ==================== 右侧：执行面板 ==================== */}
      <ExecutionDrawer />
```

- [ ] **Step 7: 新请求开始时 reset executionStore**

在 `useAgentChat.ts` 的 `handleSend` 函数（或 `doStreamRequest` 被调用处）中，在发起新请求前调用:

```typescript
// 在 handleSend / doSend 中，发送请求前:
useExecutionStore.getState().reset();
```

这个改动在 `useAgentChat.ts` 中。需要在 `useAgentChat.ts` 顶部添加 import:
```typescript
import { useExecutionStore } from '../stores/executionStore';
```

并在 `handleSend` 函数中，`doStreamRequest(...)` 调用之前添加:
```typescript
useExecutionStore.getState().reset();
```

- [ ] **Step 8: Type-check 验证**

```bash
npm run type-check
```

- [ ] **Step 9: 手动验证**

```bash
npm run dev
```

验证步骤:
1. 打开 `http://127.0.0.1:5173`，进入任意 Agent 会话
2. 发送一个数据分析问题
3. 观察:
   - 思考气泡出现并随进度刷新
   - 右侧抽屉自动滑入，显示 Round 1 Explorer
   - Tool 逐条出现，状态从 running → done
   - ReportGenerator 完成后，Analyst round done，Round 3 Reporter 出现
   - 报告渲染后 1 秒思考气泡淡出
   - 抽屉顶部显示 "✓ 执行完成"
4. 发送一个闲聊问题: 抽屉不打开，无思考气泡
5. 点击执行中 Stop 按钮: 所有 running → skipped

- [ ] **Step 10: Commit**

```bash
git add src/views/AgentRun.tsx src/hooks/useAgentChat.ts
git commit -m "feat: integrate ExecutionDrawer + ThinkingBubble into AgentRun layout"
```

---

# 第二部分: 后端实施 (Phase 2 — V3.0 渐进升级)

## 实施约定

- Python 3.12+ / FastAPI / LangGraph
- 遵循现有 WorkflowNode 基类模式
- 改动向后兼容: 新字段全部可选，前端 graceful degrade
- 测试: `pytest tests/ -v` 确保 174 passed

---

### Task 9: SSEPayload 协议升级

**文件:**
- Modify: `app/workflows/node_base.py`

**说明**: SSEPayload 新增 4 个可选字段。Controller 透传，前端按需使用。

- [ ] **Step 1: 扩展 SSEPayload dataclass**

```python
# app/workflows/node_base.py (修改 SSEPayload 类)

@dataclass
class SSEPayload:
    """节点对前端的自描述输出 — Controller 只转发，不解析

    Java 对应: GraphNodeResponse 的 text + textType 字段

    V3.0 新增字段 (全部可选):
      - agent_name:  所属 Agent (Explorer/Analyst/Reporter)
      - tool_name:   当前 tool 名称 (get_schema / execute_sql / ...)
      - tool_status: pending / running / done / error
      - tool_summary: tool 结果摘要 (单行, < 80 字符)
    """
    text: str
    text_type: str = "TEXT"  # SQL | JSON | HTML | MARK_DOWN | RESULT_SET | PYTHON | TEXT
    metrics_delta: Dict[str, Any] = field(default_factory=dict)
    # V3.0 可选字段
    agent_name: Optional[str] = None    # Explorer | Analyst | Reporter
    tool_name: Optional[str] = None     # get_schema | execute_sql | ...
    tool_status: Optional[str] = None   # pending | running | done | error
    tool_summary: Optional[str] = None  # 单行摘要
```

需要确认 `Optional` 已 import:
```python
from typing import Any, Dict, List, Optional
```

(当前只有 `Any, Dict, List, Optional` 在 line 17 — 检查 import)

- [ ] **Step 2: 运行现有测试**

```bash
cd C:/Users/Zhangwenye/Desktop/data-analysis-agent/data-agent-backend
python -m pytest tests/ -v
```

预期: 174 passed (新增字段为可选，不影响现有节点)

- [ ] **Step 3: Commit**

```bash
git add app/workflows/node_base.py
git commit -m "feat: add V3.0 optional fields to SSEPayload (agentName/toolName/toolStatus/toolSummary)"
```

---

### Task 10: Controller 透传新字段

**文件:**
- Modify: `app/api/streaming_graph_controller.py`

- [ ] **Step 1: 修改 _build_graph_response 支持新字段**

```python
# streaming_graph_controller.py

def _build_graph_response(
    agent_id: int,
    thread_id: str,
    node_name: str,
    text: str,
    text_type: str = "TEXT",
    error: bool = False,
    complete: bool = False,
    # V3.0 可选字段
    agent_name: str | None = None,
    tool_name: str | None = None,
    tool_status: str | None = None,
    tool_summary: str | None = None,
) -> dict:
    """构建 GraphNodeResponse 响应"""
    response = {
        "agentId": str(agent_id),
        "threadId": thread_id or "",
        "nodeName": node_name,
        "textType": text_type,
        "text": text or "",
        "error": error,
        "complete": complete,
    }
    # V3.0 可选字段: 仅非 None 时序列化
    if agent_name is not None:
        response["agentName"] = agent_name
    if tool_name is not None:
        response["toolName"] = tool_name
    if tool_status is not None:
        response["toolStatus"] = tool_status
    if tool_summary is not None:
        response["toolSummary"] = tool_summary
    return response
```

- [ ] **Step 2: 修改通用 SSE 输出处读取新字段**

找到 `stream_workflow_execution` 中的通用 SSE 输出段 (大约 line 442-446):

```python
# 当前:
if sse:
    yield _format_logged_sse_data(_build_graph_response(
        agent_id, thread_id, java_name, sse["text"], sse["textType"]
    ))
```

改为:

```python
# V3.0: 透传 agentName/toolName/toolStatus/toolSummary
if sse:
    yield _format_logged_sse_data(_build_graph_response(
        agent_id, thread_id, java_name, sse["text"], sse["textType"],
        agent_name=sse.get("agentName"),
        tool_name=sse.get("toolName"),
        tool_status=sse.get("toolStatus"),
        tool_summary=sse.get("toolSummary"),
    ))
```

**关键**: `sse["text"]` 和 `sse["textType"]` 来自 `node_output["sse_output"]` (base class 注入的 dict)，现在需要 base class 同时注入 `agentName` 等字段。

- [ ] **Step 3: 修改 WorkflowNode.__call__ 注入新字段**

在 `node_base.py` 的 `__call__` 方法中，构建 `sse_output` 时传入新字段:

当前代码 (line ~120-130):
```python
if sse_payload is not None:
    result["sse_output"] = {
        "text": sse_payload.text,
        "textType": sse_payload.text_type,
    }
```

改为:
```python
if sse_payload is not None:
    sse_dict = {
        "text": sse_payload.text,
        "textType": sse_payload.text_type,
    }
    # V3.0 可选字段: Controller 透传, 前端按需使用
    if sse_payload.agent_name:
        sse_dict["agentName"] = sse_payload.agent_name
    if sse_payload.tool_name:
        sse_dict["toolName"] = sse_payload.tool_name
    if sse_payload.tool_status:
        sse_dict["toolStatus"] = sse_payload.tool_status
    if sse_payload.tool_summary:
        sse_dict["toolSummary"] = sse_payload.tool_summary
    result["sse_output"] = sse_dict
    # ★ 保留 metrics_delta: Controller 依赖 _metrics_delta 收集核心指标
    if sse_payload.metrics_delta:
        result.setdefault("_metrics_delta", {}).update(sse_payload.metrics_delta)
```

- [ ] **Step 4: 运行现有测试**

```bash
python -m pytest tests/ -v
```

预期: 174 passed

- [ ] **Step 5: Commit**

```bash
git add app/workflows/node_base.py app/api/streaming_graph_controller.py
git commit -m "feat: pass-through V3.0 SSEPayload fields in controller and base class"
```

---

### Task 11: 节点逐个声明 Agent

**文件:**
- Modify: `app/workflows/nodes/*.py` (17 个节点)

**说明**: 每个节点的 `format_sse()` 返回的 `SSEPayload` 中添加 `agent_name`/`tool_name` 声明。按 spec §7.1 映射表。

- [ ] **Step 1: Explorer 4 个节点**

**schema_recall.py** — `format_sse()` 中:
```python
return SSEPayload(
    text=f"正在加载数据库表结构...找到 {len(schema_info)} 张表",
    text_type="TEXT",
    agent_name="Explorer",
    tool_name="get_schema",
    tool_status="done",
    tool_summary=f"找到 {len(schema_info)} 张表",
)
```

**knowledge_recall.py** (路径: `app/workflows/nodes/knowledge_recall.py`):
```python
return SSEPayload(
    text=...,
    text_type="TEXT",
    agent_name="Explorer",
    tool_name="search_knowledge",
    tool_status="done",
    tool_summary=f"召回 {len(items)} 条知识",
)
```

**query_rewrite.py**:
```python
return SSEPayload(
    text=...,
    text_type="TEXT",
    agent_name="Explorer",
    tool_name="rewrite_query",
    tool_status="done",
)
```

**table_relation.py**:
```python
return SSEPayload(
    text=...,
    text_type="TEXT",
    agent_name="Explorer",
    tool_name="find_relations",
    tool_status="done",
    tool_summary=f"发现 {len(relations)} 条表关联",
)
```

- [ ] **Step 2: Analyst 6 个节点**

**sql_generate.py**:
```python
return SSEPayload(
    text=sql,
    text_type="SQL",
    agent_name="Analyst",
    tool_name="text_to_sql",
    tool_status="done",
    metrics_delta={"sql_generated": True},
)
```

**semantic_consistency.py**:
```python
return SSEPayload(
    text=...,
    text_type="TEXT",
    agent_name="Analyst",
    tool_name="semantic_check",
    tool_status="done" if passed else "error",
)
```

**sql_execute.py**:
```python
return SSEPayload(
    text=...,
    text_type="RESULT_SET",
    agent_name="Analyst",
    tool_name="execute_sql",
    tool_status="error" if sql_error else "done",
    tool_summary=f"{len(rows)} 行" if not sql_error else str(sql_error)[:80],
)
```

**python_generate.py**:
```python
return SSEPayload(
    text=...,
    text_type="PYTHON",
    agent_name="Analyst",
    tool_name="text_to_python",
    tool_status="done",
)
```

**python_execute.py**:
```python
return SSEPayload(
    text=...,
    text_type="TEXT",
    agent_name="Analyst",
    tool_name="run_python",
    tool_status="error" if not success else "done",
)
```

**python_analyze.py**:
```python
return SSEPayload(
    text=...,
    text_type="TEXT",
    agent_name="Analyst",
    tool_name="analyze_result",
    tool_status="done",
)
```

- [ ] **Step 3: Reporter 节点**

**report_generator.py**:
```python
return SSEPayload(
    text=html_report,
    text_type="HTML",
    agent_name="Reporter",
    tool_status="done",
    metrics_delta={"report_generated": True},
)
```

- [ ] **Step 4: 编排节点 (无 tool)**

`feasibility.py`, `planner.py`, `plan_executor.py`, `human_feedback_node.py`, `chitchat_node.py`, `intent_recognition.py`:

这些节点或无需声明 `agent_name`（编排节点），或仅设置 `agent_name` 不设置 `tool_name`。按需添加即可，无强制要求—前端通过 nodeName infer。

- [ ] **Step 5: 运行测试 + Commit**

```bash
python -m pytest tests/ -v
# 预期: 174 passed

git add app/workflows/nodes/
git commit -m "feat: declare agentName/toolName in 17 node format_sse() methods"
```

---

# 第三部分: 跨仓库集成验证

在所有代码改动完成后，执行完整的端到端验证:

- [ ] **集成验证 1: 数据分析问题完整链路**

```bash
# Terminal 1: 启动后端
cd C:/Users/Zhangwenye/Desktop/data-analysis-agent/data-agent-backend
python main.py

# Terminal 2: 启动前端
cd C:/Users/Zhangwenye/Desktop/data-analysis-agent/data-agent-fronted
npm run dev
```

1. 打开浏览器 `http://127.0.0.1:5173`
2. 进入一个已配置数据源的 Agent
3. 发送: "上月各品类 GMV 趋势"
4. 观察:
   - 思考气泡出现 "正在召回业务知识…"
   - 右侧抽屉滑入 Round 1 Explorer
   - Tool 逐条: search_knowledge → rewrite_query → get_schema → find_relations
   - Round 2 Analyst 出现: text_to_sql → semantic_check → execute_sql
   - 思考气泡刷新 "正在生成 SQL 查询…" → "正在执行 SQL 查询…"
   - Round 3 Reporter 出现
   - AI 回复气泡渲染后 1 秒思考气泡消失
   - 抽屉顶部显示 "✓ 执行完成"

- [ ] **集成验证 2: 闲聊问题**

发送: "你好"
- 思考气泡不出现
- 抽屉不打开
- 正常显示 AI 回复

- [ ] **集成验证 3: 停止按钮**

发送数据分析问题后，在执行中点击 Stop:
- 所有 running tool → skipped (灰色 —)
- 思考气泡立即消失
- 抽屉保持可见

- [ ] **集成验证 4: HumanFeedback**

发送问题 (需要开启 humanFeedback 开关):
- 执行到 HumanFeedbackNode 时, 思考气泡 "等待人工确认…"
- 确认后流程继续
- 抽屉状态正常

---

# 附录 A: 关键接口契约 (前后端约定)

## SSE 消息格式

```json
// data: 消息 (node 输出)
{
  "agentId": "1",
  "threadId": "uuid-xxx",
  "nodeName": "SchemaRecallNode",
  "textType": "TEXT",
  "text": "正在加载数据库表结构...找到 5 张表",
  "error": false,
  "complete": false,
  "agentName": "Explorer",       // V3.0+
  "toolName": "get_schema",      // V3.0+
  "toolStatus": "running",       // V3.0+
  "toolSummary": "找到 5 张表"   // V3.0+
}

// event: complete
// event: error
// event: paused
```

## 前端 nodeName → Agent 映射 (Phase 1 硬编码, Phase 2 后端发送)

| nodeName (SSE) | agentName | toolName | thinkingText |
|----------------|-----------|----------|-------------|
| EvidenceRecallNode | Explorer | search_knowledge | 正在召回业务知识… |
| QueryEnhanceNode | Explorer | rewrite_query | 正在改写查询… |
| SchemaRecallNode | Explorer | get_schema | 正在探查数据表结构… |
| TableRelationNode | Explorer | find_relations | 正在分析表关联关系… |
| FeasibilityAssessmentNode | — | — | 正在制定执行计划… |
| PlannerNode | — | — | 正在制定执行计划… |
| IntentRecognitionNode | — | — | (不展示) |
| PlanExecutorNode | — | — | 正在执行步骤… |
| SqlGenerateNode | Analyst | text_to_sql | 正在生成 SQL 查询… |
| SemanticConsistencyNode | Analyst | semantic_check | 正在校验语义一致性… |
| SqlExecuteNode | Analyst | execute_sql | 正在执行 SQL 查询… |
| PythonGenerateNode | Analyst | text_to_python | 正在生成分析代码… |
| PythonExecuteNode | Analyst | run_python | 正在执行 Python 分析… |
| PythonAnalyzeNode | Analyst | analyze_result | 正在解读分析结果… |
| ReportGeneratorNode | Reporter | — | 正在生成分析报告… |
| HumanFeedbackNode | — | — | 等待人工确认… |
| ChitchatNode | — | — | (不展示) |

---

# 附录 B: Phase 3 — V3.0 架构迁移 (参考)

Phase 2 完成后，SSE 协议已支持 `agentName`/`toolName`/`toolStatus`/`toolSummary`。Phase 3 将 16 节点固定流水线重构为 3 Agent ReAct subgraph，详见:

- Spec: `docs/superpowers/specs/2026-05-18-multi-agent-architecture-design.md`

Phase 3 完成后前端 switch 可简化为:

```typescript
// V3.0: 不再需要 NODE_TO_EXECUTION 映射表
// 直接通过 payload.agentName / payload.toolName 驱动 UI
if (payload.agentName && payload.roundIndex) {
  execStore.upsertRound(payload.agentName, payload.roundIndex)
}
if (payload.toolName) {
  execStore.addToolCall(payload.agentName, {
    name: payload.toolName,
    status: payload.toolStatus || 'running',
  })
}
```
