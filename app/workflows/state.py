"""工作流状态定义 — 对齐 Java DataAgent OverAllState"""
from typing import TypedDict, Optional, List, Dict, Any, Union


class WorkflowState(TypedDict, total=False):
    """工作流状态 — 对齐 Java Constant.java 的 State Key 体系"""

    # ========== 输入层 ==========
    agent_id: int                    # AGENT_ID
    user_query: str                  # INPUT_KEY
    is_only_nl2sql: bool             # IS_ONLY_NL2SQL — NL2SQL Only 模式
    multi_turn_context: str          # MULTI_TURN_CONTEXT — 多轮对话上下文

    # ========== 意图识别 ==========
    intent: Optional[str]            # INTENT_RECOGNITION_NODE_OUTPUT — "data_analysis" | "chitchat"

    # ========== 知识召回 (RAG Evidence) ==========
    recalled_knowledge: Optional[str]             # EVIDENCE — 召回的知识证据文本
    knowledge_items: Optional[List[Dict[str, Any]]]  # 知识项列表
    recalled_business_terms: Optional[str]        # 业务知识
    recalled_agent_knowledge: Optional[str]       # 智能体知识

    # ========== 查询增强 ==========
    rewritten_query: Optional[str]    # QUERY_ENHANCE_NODE_OUTPUT — 改写后的规范化查询
    canonical_query: Optional[str]    # 规范查询（等同 rewritten_query）

    # ========== 数据库 Schema ==========
    schema: Optional[str]                         # TABLE_RELATION_OUTPUT — LLM 使用的文本 DDL
    schema_info: Optional[Dict[str, Any]]         # 结构化的 schema 数据
    table_documents: Optional[List[Any]]          # TABLE_DOCUMENTS_FOR_SCHEMA
    column_documents: Optional[List[Any]]         # COLUMN_DOCUMENTS__FOR_SCHEMA
    db_dialect_type: Optional[str]               # DB_DIALECT_TYPE — 数据库方言
    semantic_model_prompt: Optional[str]          # GENEGRATED_SEMANTIC_MODEL_PROMPT

    # ========== 表关系 ==========
    table_relation_exception: Optional[str]         # TABLE_RELATION_EXCEPTION_OUTPUT
    table_relation_retry_count: Optional[int]       # TABLE_RELATION_RETRY_COUNT

    # ========== 可行性评估 ==========
    feasibility_result: Optional[Dict[str, Any]]    # FEASIBILITY_ASSESSMENT_NODE_OUTPUT

    # ========== 计划生成 (Planner) ==========
    query_plan: Optional[Dict[str, Any]]         # PLANNER_NODE_OUTPUT — Plan 对象 JSON
    is_complex_query: Optional[bool]

    # ========== 计划执行调度 (PlanExecutor) ==========
    plan_current_step: int                       # PLAN_CURRENT_STEP — 当前步骤编号 (从1开始)
    plan_next_node: Optional[str]                # PLAN_NEXT_NODE — 下一个路由目标节点
    plan_validation_status: Optional[bool]       # PLAN_VALIDATION_STATUS — 校验是否通过
    plan_validation_error: Optional[str]         # PLAN_VALIDATION_ERROR — 校验/拒绝错误信息
    plan_repair_count: int                       # PLAN_REPAIR_COUNT — 修复尝试次数

    # ========== SQL 生成 ==========
    generated_sql: Optional[str]                 # SQL_GENERATE_OUTPUT — 生成的 SQL
    sql_generate_count: int                      # SQL_GENERATE_COUNT — 重试计数
    sql_regenerate_reason: Optional[Dict[str, Any]]  # SQL_REGENERATE_REASON — 重试原因 {type, reason}

    # ========== 语义一致性校验 ==========
    semantic_consistency_result: Optional[bool]  # SEMANTIC_CONSISTENCY_NODE_OUTPUT

    # ========== SQL 执行 ==========
    sql_result: Optional[List[Dict[str, Any]]]   # SQL_EXECUTE_NODE_OUTPUT (聚合)
    sql_result_list_memory: Optional[List[Dict[str, Any]]]  # SQL_RESULT_LIST_MEMORY — 所有步骤的SQL结果列表
    sql_error: Optional[str]
    sql_retry_count: int                         # 兼容旧代码，等同 sql_generate_count
    sql_step_results: Optional[Dict[str, Any]]   # 按步骤存储的 SQL 执行结果 {"step_1": ..., "step_2": ...}

    # ========== 图表配置 ==========
    display_style: Optional[Dict[str, Any]]      # 图表配置推荐结果

    # ========== Python 分析 ==========
    python_code: Optional[str]                   # PYTHON_GENERATE_NODE_OUTPUT
    python_output: Optional[str]                 # PYTHON_EXECUTE_NODE_OUTPUT
    python_error: Optional[str]
    python_charts: Optional[List[str]]
    python_data: Optional[Any]
    python_analysis: Optional[str]               # PYTHON_ANALYSIS_NODE_OUTPUT
    python_is_success: Optional[bool]            # PYTHON_IS_SUCCESS — 执行是否成功
    python_tries_count: int                      # PYTHON_TRIES_COUNT — 重试计数
    python_fallback_mode: Optional[bool]         # PYTHON_FALLBACK_MODE — 降级模式标记

    # ========== Human Feedback ==========
    human_review_enabled: Optional[bool]         # HUMAN_REVIEW_ENABLED — 人工复核开关
    human_feedback_data: Optional[Dict[str, Any]]  # HUMAN_FEEDBACK_DATA — 反馈数据
    human_next_node: Optional[str]               # HumanFeedback 路由目标

    # ========== 报告 ==========
    report: Optional[str]                        # RESULT — Markdown 报告
    html_report: Optional[str]
    markdown_report: Optional[str]

    # ========== 错误/追踪 ==========
    error: Optional[str]
    trace_thread_id: Optional[str]               # TRACE_THREAD_ID — 追踪 ID


# 别名，兼容旧代码
AgentState = WorkflowState


def get_canonical_query(state: WorkflowState) -> str:
    """从 State 中获取规范查询 (对齐 Java StateUtil.getCanonicalQuery)"""
    return state.get("rewritten_query") or state.get("canonical_query") or state["user_query"]


def get_current_step_number(state: WorkflowState) -> int:
    """获取当前执行步骤编号 (从1开始, 对齐 Java PlanProcessUtil.getCurrentStepNumber)"""
    return state.get("plan_current_step", 1)


def get_current_instruction(state: WorkflowState) -> str:
    """获取当前执行步骤的 instruction (对齐 Java getCurrentExecutionStepInstruction)"""
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
