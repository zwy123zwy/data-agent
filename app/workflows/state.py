"""
工作流状态定义 — 对齐 Java DataAgent OverAllState + Constant.java

【在系统中的地位】
  本文件是 LangGraph 工作流的"血液系统"——WorkflowState 对象在 16 个节点之间
  流转，每个节点从中读取输入、写入输出。所有节点共享同一个 state 字典。

【模块连接】
  上游 (谁创建 state):
    - streaming_graph_controller.py  → _build_initial_state() 创建初始 state
    - graph_controller.py           → 同步查询也在此创建 state

  下游 (谁读写 state):
    - workflows/nodes/*.py (16 个节点) → 每个节点读取/写入 state 的特定 key
    - workflows/graph.py               → 路由函数读取 state 决定下一个节点

  Java 对应:
    本文件 = OverAllState.java + Constant.java (二者合一)
    StateKeys = Constant.java 中的 STATE_* 常量
    WorkflowState = OverAllState 的 TypedDict 等价

【state 的生命周期】
  1. 用户请求进入 → _build_initial_state() 创建初始 state (只有 input 层有值)
  2. 每个节点执行 → 节点函数读取 state 中的某些 key，写入新的 kv
  3. 路由函数读取 → graph.py 中的 route_after_* 函数根据 state 决定跳转
  4. 最终 → report_generator 写入最终报告，流结束
"""
from typing import TypedDict, Optional, List, Dict, Any


# ============================================================================
# StateKeys — 对齐 Java Constant.java，消除魔法字符串
#
# 【为什么需要 StateKeys】
#   Python TypedDict 的 key 是字符串，直接用 "agent_id" 容易拼写错误。
#   StateKeys 类将所有 key 集中定义为类属性，IDE 可以自动补全。
#   等价于 Java 中 Constant.java 的 public static final String 常量。
# ============================================================================

class StateKeys:
    """State Key 常量定义，对齐 Java Constant.java"""

    # ── 输入层 ──
    AGENT_ID = "agent_id"
    USER_QUERY = "user_query"
    IS_ONLY_NL2SQL = "is_only_nl2sql"
    MULTI_TURN_CONTEXT = "multi_turn_context"

    # ── 意图识别 ──
    INTENT = "intent"

    # ── 知识召回 (RAG Evidence) ──
    RECALLED_KNOWLEDGE = "recalled_knowledge"
    KNOWLEDGE_ITEMS = "knowledge_items"
    RECALLED_BUSINESS_TERMS = "recalled_business_terms"
    RECALLED_AGENT_KNOWLEDGE = "recalled_agent_knowledge"

    # ── 查询增强 ──
    REWRITTEN_QUERY = "rewritten_query"
    CANONICAL_QUERY = "canonical_query"

    # ── Schema ──
    SCHEMA = "schema"
    SCHEMA_INFO = "schema_info"
    TABLE_DOCUMENTS = "table_documents"
    COLUMN_DOCUMENTS = "column_documents"
    DB_DIALECT_TYPE = "db_dialect_type"
    SEMANTIC_MODEL_PROMPT = "semantic_model_prompt"

    # ── 表关系 ──
    TABLE_RELATION_EXCEPTION = "table_relation_exception"
    TABLE_RELATION_RETRY_COUNT = "table_relation_retry_count"

    # ── 可行性评估 ──
    FEASIBILITY_RESULT = "feasibility_result"

    # ── Planner ──
    QUERY_PLAN = "query_plan"
    IS_COMPLEX_QUERY = "is_complex_query"

    # ── PlanExecutor ──
    PLAN_CURRENT_STEP = "plan_current_step"
    PLAN_NEXT_NODE = "plan_next_node"
    PLAN_VALIDATION_STATUS = "plan_validation_status"
    PLAN_VALIDATION_ERROR = "plan_validation_error"
    PLAN_REPAIR_COUNT = "plan_repair_count"

    # ── SQL 生成 ──
    GENERATED_SQL = "generated_sql"
    SQL_GENERATE_COUNT = "sql_generate_count"
    SQL_REGENERATE_REASON = "sql_regenerate_reason"

    # ── 语义一致性 ──
    SEMANTIC_CONSISTENCY_RESULT = "semantic_consistency_result"

    # ── SQL 执行 ──
    SQL_RESULT = "sql_result"
    SQL_RESULT_LIST_MEMORY = "sql_result_list_memory"
    SQL_ERROR = "sql_error"
    SQL_RETRY_COUNT = "sql_retry_count"
    SQL_STEP_RESULTS = "sql_step_results"

    # ── 图表配置 ──
    DISPLAY_STYLE = "display_style"

    # ── Python 分析 ──
    PYTHON_CODE = "python_code"
    PYTHON_OUTPUT = "python_output"
    PYTHON_ERROR = "python_error"
    PYTHON_CHARTS = "python_charts"
    PYTHON_DATA = "python_data"
    PYTHON_ANALYSIS = "python_analysis"
    PYTHON_IS_SUCCESS = "python_is_success"
    PYTHON_TRIES_COUNT = "python_tries_count"
    PYTHON_FALLBACK_MODE = "python_fallback_mode"

    # ── Human Feedback ──
    HUMAN_REVIEW_ENABLED = "human_review_enabled"
    HUMAN_FEEDBACK_DATA = "human_feedback_data"
    HUMAN_NEXT_NODE = "human_next_node"

    # ── 报告 ──
    REPORT = "report"
    HTML_REPORT = "html_report"
    MARKDOWN_REPORT = "markdown_report"

    # ── 错误/追踪 ──
    ERROR = "error"
    TRACE_THREAD_ID = "trace_thread_id"


# ============================================================================
# WorkflowState — 对齐 Java OverAllState
# ============================================================================

class WorkflowState(TypedDict, total=False):
    """工作流状态 — LangGraph 全局共享字典

    这是整个工作流系统的"血液"——所有 16 个节点通过读写同一个 state 字典
    来传递信息。每个节点执行后，LangGraph 自动将返回值合并回 state。

    【TypedDict vs Java OverAllState】
      Java: OverAllState 是 Map<String, Object>，用 Constant.java 定义 key
      Python: WorkflowState 是 TypedDict，用 StateKeys 定义 key
      两者本质上都是 key-value 字典，但 TypedDict 提供类型提示

    【读写者关系】
      每个 state key 都有"生产者"（写入节点）和"消费者"（读取节点）:

      生产者                    State Key                消费者
      ─────────────────────────────────────────────────────────
      streaming_graph_ctrl  →  agent_id              →  nodes/*.py (所有节点)
      streaming_graph_ctrl  →  user_query            →  intent_recognition, planner, ...
      intent_recognition    →  intent                →  route_after_intent
      knowledge_recall      →  recalled_knowledge    →  query_rewrite, planner
      query_rewrite         →  rewritten_query       →  schema_recall, planner
      schema_recall         →  schema                →  table_relation, sql_generate
      table_relation        →  schema_info           →  feasibility, planner
      feasibility           →  feasibility_result    →  route_after_feasibility
      planner               →  query_plan            →  plan_executor
      plan_executor         →  plan_next_node        →  route_after_plan_executor
      sql_generate          →  generated_sql         →  semantic_consistency, sql_execute
      sql_execute           →  sql_result            →  python_generate, report_generator
      python_generate       →  python_code           →  python_execute
      python_execute        →  python_output         →  python_analyze
      report_generator      →  report/html_report    →  streaming_graph_ctrl (SSE 输出)

    ┌─────────────────────────────────────────────────────┐
    │ 状态分组总览                                          │
    │                                                       │
    │  1. INPUT     — 输入层 (agent_id, user_query, ...)     │
    │  2. INTENT    — 意图识别 (intent)                      │
    │  3. RAG       — 知识召回 (recalled_*, knowledge_*)    │
    │  4. QUERY     — 查询增强 (rewritten_query, ...)        │
    │  5. SCHEMA    — Schema & 表关系 (schema, table_*, ...)│
    │  6. PLAN      — Planner & Executor (query_plan, ...)   │
    │  7. SQL       — SQL 流水线 (generated_sql, ...)        │
    │  8. DISPLAY   — 图表样式 (display_style)              │
    │  9. PYTHON    — Python 分析 (python_*, ...)           │
    │ 10. FEEDBACK  — 人工复核 (human_*, ...)               │
    │ 11. REPORT    — 报告输出 (report, html_report, ...)    │
    │ 12. TRACE     — 追踪 (trace_thread_id, error)         │
    └─────────────────────────────────────────────────────┘
    """

    # =====================================================================
    # 1. INPUT 层 — 用户输入 & 会话上下文
    # =====================================================================
    agent_id: int
    user_query: str
    is_only_nl2sql: bool
    multi_turn_context: str

    # =====================================================================
    # 2. INTENT — 意图识别
    # =====================================================================
    intent: Optional[str]

    # =====================================================================
    # 3. RAG — 知识召回 (Evidence Recall)
    # =====================================================================
    recalled_knowledge: Optional[str]
    knowledge_items: Optional[List[Dict[str, Any]]]
    recalled_business_terms: Optional[str]
    recalled_agent_knowledge: Optional[str]

    # =====================================================================
    # 4. QUERY — 查询增强
    # =====================================================================
    rewritten_query: Optional[str]
    canonical_query: Optional[str]

    # =====================================================================
    # 5. SCHEMA — 数据库 Schema & 表关系
    # =====================================================================
    schema: Optional[str]
    schema_info: Optional[Dict[str, Any]]
    table_documents: Optional[List[Any]]
    column_documents: Optional[List[Any]]
    db_dialect_type: Optional[str]
    semanti_model_prompt: Optional[str]
    table_relation_exception: Optional[str]
    table_relation_retry_count: Optional[int]

    # =====================================================================
    # 6. PLAN — 计划 & 执行调度
    # =====================================================================
    feasibility_result: Optional[Dict[str, Any]]
    query_plan: Optional[Dict[str, Any]]
    is_complex_query: Optional[bool]
    plan_current_step: int
    plan_next_node: Optional[str]
    plan_validation_status: Optional[bool]
    plan_validation_error: Optional[str]
    plan_repair_count: int

    # =====================================================================
    # 7. SQL — SQL 流水线 (生成 → 校验 → 执行)
    # =====================================================================
    generated_sql: Optional[str]
    sql_generate_count: int
    sql_regenerate_reason: Optional[Dict[str, Any]]
    semanti_consistency_result: Optional[bool]
    sql_result: Optional[List[Dict[str, Any]]]
    sql_result_list_memory: Optional[List[Dict[str, Any]]]
    sql_error: Optional[str]
    sql_retry_count: int
    sql_step_results: Optional[Dict[str, Any]]

    # =====================================================================
    # 8. DISPLAY — 图表配置
    # =====================================================================
    display_style: Optional[Dict[str, Any]]

    # =====================================================================
    # 9. PYTHON — Python 分析流水线 (生成 → 执行 → 分析)
    # =====================================================================
    python_code: Optional[str]
    python_output: Optional[str]
    python_error: Optional[str]
    python_charts: Optional[List[str]]
    python_data: Optional[Any]
    python_analysis: Optional[str]
    python_is_success: Optional[bool]
    python_tries_count: int
    python_fallback_mode: Optional[bool]

    # =====================================================================
    # 10. FEEDBACK — 人工复核
    # =====================================================================
    human_review_enabled: Optional[bool]
    human_feedback_data: Optional[Dict[str, Any]]
    human_next_node: Optional[str]

    # =====================================================================
    # 11. REPORT — 报告输出
    # =====================================================================
    report: Optional[str]
    html_report: Optional[str]
    markdown_report: Optional[str]

    # =====================================================================
    # 12. TRACE — 错误 & 追踪
    # =====================================================================
    error: Optional[str]
    trace_thread_id: Optional[str]


# ============================================================================
# 辅助函数 — 对齐 Java StateUtil / PlanProcessUtil
#
# 【模块连接】
#   这些函数被 nodes/*.py 中的节点函数调用，用于从 state 中提取信息。
#   它们不是节点，是纯工具函数——不修改 state，只读取。
#
#   调用者:
#     - get_canonical_query()    → sql_generate, python_generate, knowledge_recall
#     - get_current_step_number() → plan_executor, sql_generate, python_generate
#     - get_current_instruction() → sql_generate, python_generate (作为 LLM prompt 的一部分)
# ============================================================================

def get_canonical_query(state: WorkflowState) -> str:
    """获取规范查询 — 对齐 Java StateUtil.getCanonicalQuery

    优先级: rewritten_query > canonical_query > 原始 user_query
    用途: 作为 LLM 生成 SQL/Python 时的输入文本
    """
    return state.get("rewritten_query") or state.get("canonical_query") or state["user_query"]


def get_current_step_number(state: WorkflowState) -> int:
    """获取当前执行步骤编号 (从1开始) — 对齐 Java PlanProcessUtil.getCurrentStepNumber

    被 plan_executor 在每次循环时递增，指示当前正在执行计划的第几步
    """
    return state.get("plan_current_step", 1)


def get_current_instruction(state: WorkflowState) -> str:
    """获取当前执行步骤的 instruction — 对齐 Java getCurrentExecutionStepInstruction

    从 query_plan.execution_plan[current_step] 中提取当前步骤描述
    作为 LLM 生成 SQL/Python 代码时的具体指令
    """
    plan = state.get("query_plan")
    if not plan:
        return state.get("user_query", "")
    steps = plan.get("execution_plan") or plan.get("steps", [])
    current = get_current_step_number(state) - 1
    if 0 <= current < len(steps):
        step = steps[current]
        tp = step.get("tool_parameters") or {}
        return tp.get("instruction", step.get("description", ""))
    return state.get("user_query", "")
