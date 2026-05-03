"""工作流状态定义 — 对齐 Java DataAgent OverAllState + Constant.java"""
from typing import TypedDict, Optional, List, Dict, Any


# ============================================================================
# StateKeys — 对齐 Java Constant.java，消除魔法字符串
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
    """工作流状态 — 对齐 Java Constant.java 的 State Key 体系

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
    │  8. PYTHON    — Python 分析 (python_*, ...)           │
    │  9. FEEDBACK  — 人工复核 (human_*, ...)               │
    │ 10. REPORT    — 报告输出 (report, html_report, ...)    │
    │ 11. TRACE     — 追踪 (trace_thread_id, error)         │
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
# ============================================================================

def get_canonical_query(state: WorkflowState) -> str:
    """获取规范查询 — 对齐 Java StateUtil.getCanonicalQuery"""
    return state.get("rewritten_query") or state.get("canonical_query") or state["user_query"]


def get_current_step_number(state: WorkflowState) -> int:
    """获取当前执行步骤编号 (从1开始) — 对齐 Java PlanProcessUtil.getCurrentStepNumber"""
    return state.get("plan_current_step", 1)


def get_current_instruction(state: WorkflowState) -> str:
    """获取当前执行步骤的 instruction — 对齐 Java getCurrentExecutionStepInstruction"""
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
