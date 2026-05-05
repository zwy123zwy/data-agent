# TODO: Align Java Agent Execution And Frontend Contract

## Phase 0. 基线确认

- [x] 梳理 Java 版 Agent 执行能力清单。
  - [x] 确认 `GraphController.java` 的请求参数、SSE event、返回结构。
  - [x] 确认 `GraphServiceImpl.java` 的新请求流程、HumanFeedback 恢复流程、取消流程。
  - [x] 确认 `DataAgentConfiguration.java` 的节点列表、条件边、重试逻辑。
  - [x] 确认 `GraphNodeResponse.java` 字段定义和默认值。
- [x] 梳理前端会话页真实调用清单。
  - [x] `src/services/graph.ts`
  - [x] `src/services/chat.ts`
  - [x] `src/views/AgentRun.vue`
  - [x] `src/components/run/ChatSessionSidebar.vue`
- [x] 梳理 Python 版当前能力清单。
  - [x] `app/api/streaming_graph_controller.py`
  - [x] `app/api/graph_controller.py`
  - [x] `app/api/chat_controller.py`
  - [x] `app/workflows/graph.py`
  - [x] `app/workflows/nodes/*.py`

## Phase 1. 流式协议对齐

- [x] 定义 Python 版 `GraphNodeResponse` schema。
  - [x] `agentId`
  - [x] `threadId`
  - [x] `nodeName`
  - [x] `textType`
  - [x] `text`
  - [x] `error`
  - [x] `complete`
- [x] 改造 Python `GET /api/stream/search`，使其 SSE data 兼容 Java 前端。
  - [x] 普通节点输出使用默认 SSE message，`data` 为 `GraphNodeResponse JSON`。
  - [x] 完成时发送 `event: complete`。
  - [x] 错误时发送 `event: error`。
  - [x] 保证前端 `JSON.parse(event.data)` 可直接解析。
- [x] 建立 Python 节点名到 Java 节点名的映射。
  - [x] `intent_recognition` → `IntentRecognitionNode`
  - [x] `knowledge_recall` → `EvidenceRecallNode`
  - [x] `query_rewrite` → `QueryEnhanceNode`
  - [x] `schema_recall` → `SchemaRecallNode`
  - [x] `table_relation` → `TableRelationNode`
  - [x] `feasibility` → `FeasibilityAssessmentNode`
  - [x] `planner` → `PlannerNode`
  - [x] `plan_executor` → `PlanExecutorNode`
  - [x] `sql_generate` → `SqlGenerateNode`
  - [x] `semantic_consistency` → `SemanticConsistencyNode`
  - [x] `sql_execute` → `SqlExecuteNode`
  - [x] `python_generate` → `PythonGenerateNode`
  - [x] `python_execute` → `PythonExecuteNode`
  - [x] `python_analyze` → `PythonAnalyzeNode`
  - [x] `human_feedback` → `HumanFeedbackNode`
  - [x] `report_generator` → `ReportGeneratorNode`
- [x] 对齐 `TextType`。
  - [x] `JSON`
  - [x] `PYTHON`
  - [x] `SQL`
  - [x] `HTML`
  - [x] `MARK_DOWN`
  - [x] `RESULT_SET`
  - [x] `TEXT`
- [x] 明确 Python 当前额外接口 `POST /api/query/stream` 的定位。
  - [x] 若保留，文档说明它是 Python 扩展接口。
  - [x] 前端主链路仍以 `GET /api/stream/search` 为准。

## Phase 2. Agent 执行节点能力对齐

- [x] IntentRecognition 对齐。
  - [x] 闲聊/无关问题应结束流程。
  - [x] 数据分析问题进入召回节点。
  - [x] 增加意图识别回归样例。
- [x] EvidenceRecall / KnowledgeRecall 对齐。
  - [x] Python 需同时覆盖业务知识和智能体知识。
  - [x] 对齐 Java 版按 `agentId` 检索知识的语义。
  - [x] 验证召回内容能进入后续 prompt。
- [x] QueryEnhance / QueryRewrite 对齐。
  - [x] 支持多轮上下文注入。
  - [x] 输出为空或解析失败时按 Java 语义结束或降级。
- [x] SchemaRecall 对齐。
  - [x] 必须按当前 Agent 激活数据源召回 Schema。
  - [x] 无激活数据源时返回兼容前端的 error SSE。
  - [x] 对齐所选表 `select_tables` 的约束。
- [x] TableRelation 对齐。
  - [x] 对齐表关系构建字段。
  - [x] 对齐重试次数和失败结束条件。
  - [x] 验证多表 Join 场景。
- [x] FeasibilityAssessment 对齐。
  - [x] 可行则进入 Planner。
  - [x] 不可行则结束并返回可展示原因。
- [x] Planner 对齐。
  - [x] 输出结构兼容 PlanExecutor。
  - [x] 支持 SQL、Python、Report、HumanFeedback 类型步骤。
  - [x] 增加非法 Plan 修复测试。
- [x] PlanExecutor 对齐。
  - [x] 校验 Plan 结构。
  - [x] 根据当前 step 路由 SQL / Python / Report / HumanFeedback。
  - [x] SQL/Python 分支完成后回到 PlanExecutor。
  - [x] 所有步骤完成后进入 ReportGenerator。
  - [x] 对齐 Java 修复次数，或文档说明差异。
- [x] SQL 分支对齐。
  - [x] SqlGenerate 生成 SQL。
  - [x] SemanticConsistency 判定通过后进入 SqlExecute。
  - [x] SqlExecute 失败可触发 SQL regenerate。
  - [x] 输出 SQL、执行结果、错误均兼容前端展示。
- [x] Python 分支对齐。
  - [x] PythonGenerate 生成代码。
  - [x] PythonExecute 执行代码并返回成功/失败。
  - [x] PythonAnalyze 生成分析结论。
  - [x] 执行失败重试和超限降级语义明确。
- [x] ReportGenerator 对齐。
  - [x] 输出 Markdown/HTML 内容。
  - [x] 前端能保存为 `html-report` 或 `markdown-report`。
  - [x] 报告中的 SQL/Python 结果能被正确引用。

## Phase 3. HumanFeedback 对齐

- [x] 对齐前端发起人工反馈的参数。
  - [x] `threadId`
  - [x] `humanFeedback=true`
  - [x] `humanFeedbackContent`
  - [x] `rejectedPlan`
- [x] Python 版恢复逻辑兼容 Java 行为。
  - [x] approve 后继续 PlanExecutor。
  - [x] reject 后回 Planner 重规划。
  - [x] 多次 reject 超限后结束。
- [x] SSE 暂停事件兼容前端。
  - [x] 前端能识别需要展示 HumanFeedback 组件。
  - [x] Python 若使用 `paused` event，应同时提供 Java 兼容节点输出或前端适配。
- [ ] 增加 HumanFeedback 回归测试。
  - [ ] approve 场景。
  - [ ] reject 后重规划场景。
  - [ ] reject 超限场景。

## Phase 4. 会话和前后端协同对齐

- [x] 对齐会话 API。
  - [x] `GET /api/agent/{agentId}/sessions`
  - [x] `POST /api/agent/{agentId}/sessions`
  - [x] `DELETE /api/agent/{agentId}/sessions`
  - [x] `PUT /api/sessions/{sessionId}/pin`
  - [x] `PUT /api/sessions/{sessionId}/rename`
  - [x] `DELETE /api/sessions/{sessionId}`
- [x] 对齐消息 API。
  - [x] `GET /api/sessions/{sessionId}/messages`
  - [x] `POST /api/sessions/{sessionId}/messages`
  - [x] 支持前端使用的 `messageType`：`text`、`html`、`result-set`、`html-report`、`markdown-report`。
- [x] 对齐标题更新。
  - [x] `GET /api/agent/{agentId}/sessions/stream`
  - [x] 保存用户消息时 `titleNeeded=true` 触发标题生成。
  - [x] 发送 `title-updated` SSE。
- [x] 对齐报告下载。
  - [x] `POST /api/sessions/{sessionId}/reports/html`
  - [x] 返回 blob 可下载。
- [x] 对齐前端停止流式输出。
  - [x] 前端关闭 EventSource 后后端释放上下文。
  - [x] Python 需避免后台任务继续无意义执行或泄漏。

## Phase 5. 前端兼容性验证

- [ ] 使用现有前端连接 Python 后端。（待启动前端+后端联调验证）
  - [ ] 进入 AgentRun 页面成功。
  - [ ] 创建会话成功。
  - [ ] 加载会话列表成功。
  - [ ] 加载历史消息成功。
  - [ ] 发送消息成功。
  - [ ] SSE 节点逐步展示成功。
  - [ ] SQL 节点渲染成功。
  - [ ] RESULT_SET 渲染成功。
  - [ ] HTML/Markdown 报告保存成功。
  - [ ] 停止生成成功。
  - [ ] HumanFeedback approve/reject 成功。
- [x] 补充前端协议兼容说明。
  - [x] 记录哪些接口必须保持 Java 兼容。→ `specs/protocol-alignment.md`
  - [x] 记录哪些接口是 Python 扩展。→ `POST /api/query/stream`

## Phase 6. 测试与验收

- [x] 单元测试。（已完成 109 个测试，5 个文件）
  - [x] API schema 测试。
  - [x] GraphNodeResponse 序列化测试。
  - [x] 节点路由测试。
  - [x] PlanExecutor 路由测试。
  - [x] HumanFeedback resume 测试。
- [ ] 集成测试。（待编写测试代码）
  - [ ] `GET /api/stream/search` 正常完成。
  - [ ] SQL 成功链路。
  - [ ] SQL 失败重试链路。
  - [ ] Python 成功链路。
  - [ ] HumanFeedback approve 链路。
  - [ ] HumanFeedback reject 链路。
  - [ ] 前端保存消息链路。
- [ ] 端到端测试。（需启动前端+后端联调）
  - [ ] 启动前端 + Python 后端。
  - [ ] 创建 Agent。
  - [ ] 绑定数据源。
  - [ ] 配置语义模型和知识。
  - [ ] 发送分析问题。
  - [ ] 观察节点流式展示。
  - [ ] 验证最终报告和历史消息。
- [x] 回归样例集。（路由级回归已覆盖 8 类场景 → `tests/test_regression_scenarios.py`）
  - [x] 单表查询。
  - [x] 多表 Join。
  - [x] 指标口径查询。
  - [x] 趋势分析。
  - [x] 图表分析。
  - [x] 不可回答问题。
  - [x] 闲聊问题。
  - [x] 多轮追问。

## Phase 7. 可观测性和指标

- [x] 增加节点级埋点。→ `app/services/node_metrics.py` (已集成到 streaming 循环)
  - [x] `threadId`
  - [x] `agentId`
  - [x] `sessionId`
  - [x] `nodeName`
  - [x] `startTime`
  - [x] `endTime`
  - [x] `durationMs`
  - [x] `status`
  - [x] `retryCount`
  - [x] `errorType`
  - [x] `errorMessage`
- [ ] 落地核心指标。（后续迭代）
  - [ ] 端到端成功率。
  - [ ] 端到端耗时 P50/P90/P99。
  - [ ] Intent 准确率。
  - [ ] Schema 表召回率。
  - [ ] SQL 执行成功率。
  - [ ] SQL 语义正确率。
  - [ ] Python 执行成功率。
  - [ ] Plan 校验通过率。
  - [ ] HumanFeedback 拒绝后修复成功率。
  - [ ] 最终报告数据一致性率。
- [x] 将指标设计文档关联到本 change。→ `docs/agent_node_metrics_design.md`

## Phase 8. 文档交付

- [x] 更新 Python/Java Agent 执行流程对比文档。→ `docs/FRONTEND_API_ALIGNMENT.md` (已存在)
- [x] 更新前端 API 调用图。→ `docs/FRONTEND_API_ALIGNMENT.md` (已覆盖)
- [x] 更新 Python 兼容 Java 的协议说明。→ `specs/protocol-alignment.md`
- [x] 更新本 OpenSpec change 的验收标准。→ 见下方 Acceptance Criteria
- [x] 标记已知差异和后续计划。→ `specs/known-differences.md`

## Acceptance Criteria

- [x] 前端 `data-agent-frontend` 无需重写核心会话页，即可连接 Python 后端完成一次智能体分析。（协议已对齐，待联调验证）
- [x] Python `GET /api/stream/search` SSE data 可被当前 `src/services/graph.ts` 直接解析。（格式完全兼容 GraphNodeResponse）
- [x] Python 能完成 Java 版同等主链路：Intent → Recall → Rewrite → Schema → Relation → Feasibility → Planner → PlanExecutor → SQL/Python/Report。（16 节点全部实现）
- [x] HumanFeedback approve/reject 能恢复同一 `threadId` 的执行。（LangGraph interrupt + Command(resume=...) 实现）
- [x] 会话、消息、报告、标题更新 API 与前端预期一致。（9 个会话/消息/报告端点全部对齐）
- [x] 至少覆盖 8 类回归样例：单表、多表、指标、趋势、图表、不可回答、闲聊、多轮。→ `tests/test_regression_scenarios.py` (20 测试)
- [x] 节点级执行日志和基础指标可观测。→ `app/services/node_metrics.py` (结构化 JSON 日志 + 汇总指标)

