"""
工作流图定义 — 对齐 Java DataAgentConfiguration.nl2sqlGraph

完整拓扑（PlanExecutor 循环调度）:
START → IntentRecognition
  → (chitchat) END
  → (data_analysis) KnowledgeRecall → QueryRewrite → SchemaRecall
    → TableRelation (含重试) → FeasibilityAssessment
      → (不可行) END
      → (可行) Planner → PlanExecutor (循环调度入口)
        ├→ SQL_GENERATE → SemanticConsistency → SQL_EXECUTE → PlanExecutor
        ├→ PYTHON_GENERATE → PYTHON_EXECUTE → PYTHON_ANALYZE → PlanExecutor
        ├→ REPORT_GENERATOR → END
        └→ HUMAN_FEEDBACK → (approve) PlanExecutor / (reject) Planner
"""
from typing import Literal
from langgraph.graph import StateGraph, END
from .state import WorkflowState
from .nodes.intent_recognition import intent_recognition_node
from .nodes.knowledge_recall import knowledge_recall_node
from .nodes.query_rewrite import query_rewrite_node
from .nodes.schema_recall import schema_recall_node
from .nodes.table_relation import table_relation_node
from .nodes.feasibility import feasibility_node, route_after_feasibility
from .nodes.planner import planner_node
from .nodes.plan_executor import plan_executor_node, route_after_plan_executor
from .nodes.sql_generate import sql_generate_node
from .nodes.semantic_consistency import semantic_consistency_node
from .nodes.sql_execute import sql_execute_node
from .nodes.python_generate import python_generate_node
from .nodes.python_execute import python_execute_node
from .nodes.python_analyze import python_analyze_node
from .nodes.report_generator import report_generator_node
from .nodes.human_feedback_node import human_feedback_node, route_after_human_feedback
from ..core.config import settings
import logging

logger = logging.getLogger(__name__)


# ========== 路由函数 ==========

def route_after_intent(state: WorkflowState) -> Literal["knowledge_recall", "end"]:
    """意图识别后路由 — 对齐 Java IntentRecognitionDispatcher"""
    intent = state.get("intent")
    if intent == "data_analysis":
        return "knowledge_recall"
    return "end"


def route_after_query_rewrite(state: WorkflowState) -> Literal["schema_recall", "end"]:
    """查询重写后路由 — 对齐 Java QueryEnhanceDispatcher"""
    rewritten = state.get("rewritten_query")
    if rewritten:
        return "schema_recall"
    return "end"


def route_after_schema_recall(state: WorkflowState) -> Literal["table_relation", "end"]:
    """Schema 召回后路由 — 对齐 Java SchemaRecallDispatcher"""
    schema = state.get("schema")
    if schema:
        return "table_relation"
    return "end"


def route_after_table_relation(state: WorkflowState) -> Literal["feasibility", "end", "table_relation"]:
    """表关系后路由 — 对齐 Java TableRelationDispatcher（含重试）"""
    exception = state.get("table_relation_exception")
    if not exception:
        return "feasibility"
    retry_count = state.get("table_relation_retry_count", 0)
    if retry_count < 3:
        logger.info(f"[TableRelation] Retry {retry_count + 1}/3")
        return "table_relation"
    return "end"


def route_after_sql_generate(state: WorkflowState) -> Literal["semantic_consistency", "sql_generate", "end"]:
    """SQL 生成后路由 — 对齐 Java SqlGenerateDispatcher"""
    sql = state.get("generated_sql")
    if not sql:
        count = state.get("sql_generate_count", 0)
        max_retry = settings.max_sql_retry_count
        if count >= max_retry:
            logger.error(f"[SqlGenerate] Max retry ({max_retry}) exceeded, ending")
            return "end"
        return "sql_generate"
    return "semantic_consistency"


def route_after_semantic_check(state: WorkflowState) -> Literal["sql_execute", "sql_generate"]:
    """语义校验后路由 — 对齐 Java SemanticConsistenceDispatcher"""
    passed = state.get("semantic_consistency_result", False)
    if passed:
        return "sql_execute"
    return "sql_generate"


def route_after_sql_execute(state: WorkflowState) -> Literal["plan_executor", "sql_generate"]:
    """SQL 执行后路由 — 对齐 Java SQLExecutorDispatcher"""
    error = state.get("sql_error")
    regenerate_reason = state.get("sql_regenerate_reason")
    if error or (regenerate_reason and regenerate_reason.get("type") == "execute"):
        count = state.get("sql_generate_count", 0)
        if count < settings.max_sql_retry_count:
            return "sql_generate"
    return "plan_executor"


def route_after_python_execute(state: WorkflowState) -> Literal["python_analyze", "python_generate", "end"]:
    """Python 执行后路由 — 对齐 Java PythonExecutorDispatcher"""
    is_success = state.get("python_is_success", False)
    if is_success:
        return "python_analyze"
    tries = state.get("python_tries_count", 0)
    max_tries = settings.code_executor.python_max_tries_count
    if tries >= max_tries:
        # 降级模式：直接到 analyze
        logger.warning(f"[PythonExecute] Max retries ({max_tries}) exceeded, entering fallback mode")
        return "python_analyze"
    return "python_generate"


# ========== 构建工作流图 ==========

workflow = StateGraph(WorkflowState)

# 添加所有节点
workflow.add_node("intent_recognition", intent_recognition_node)
workflow.add_node("knowledge_recall", knowledge_recall_node)
workflow.add_node("query_rewrite", query_rewrite_node)
workflow.add_node("schema_recall", schema_recall_node)
workflow.add_node("table_relation", table_relation_node)
workflow.add_node("feasibility", feasibility_node)
workflow.add_node("planner", planner_node)
workflow.add_node("plan_executor", plan_executor_node)
workflow.add_node("sql_generate", sql_generate_node)
workflow.add_node("semantic_consistency", semantic_consistency_node)
workflow.add_node("sql_execute", sql_execute_node)
workflow.add_node("python_generate", python_generate_node)
workflow.add_node("python_execute", python_execute_node)
workflow.add_node("python_analyze", python_analyze_node)
workflow.add_node("report_generator", report_generator_node)
workflow.add_node("human_feedback", human_feedback_node)

# 入口
workflow.set_entry_point("intent_recognition")

# ===== 第一阶段：前置处理链 =====
workflow.add_conditional_edges("intent_recognition", route_after_intent, {
    "knowledge_recall": "knowledge_recall",
    "end": END,
})
workflow.add_edge("knowledge_recall", "query_rewrite")
workflow.add_conditional_edges("query_rewrite", route_after_query_rewrite, {
    "schema_recall": "schema_recall",
    "end": END,
})
workflow.add_conditional_edges("schema_recall", route_after_schema_recall, {
    "table_relation": "table_relation",
    "end": END,
})
workflow.add_conditional_edges("table_relation", route_after_table_relation, {
    "feasibility": "feasibility",
    "end": END,
    "table_relation": "table_relation",
})
workflow.add_conditional_edges("feasibility", route_after_feasibility, {
    "planner": "planner",
    "end": END,
})

# ===== 第二阶段：Planner → PlanExecutor =====
workflow.add_edge("planner", "plan_executor")

# ===== 第三阶段：PlanExecutor 循环调度 =====
workflow.add_conditional_edges("plan_executor", route_after_plan_executor, {
    "sql_generate": "sql_generate",
    "python_generate": "python_generate",
    "report_generator": "report_generator",
    "human_feedback": "human_feedback",
    "planner": "planner",
    "end": END,
})

# ===== SQL 流水线 =====
workflow.add_conditional_edges("sql_generate", route_after_sql_generate, {
    "semantic_consistency": "semantic_consistency",
    "sql_generate": "sql_generate",
    "end": END,
})
workflow.add_conditional_edges("semantic_consistency", route_after_semantic_check, {
    "sql_execute": "sql_execute",
    "sql_generate": "sql_generate",
})
workflow.add_conditional_edges("sql_execute", route_after_sql_execute, {
    "plan_executor": "plan_executor",
    "sql_generate": "sql_generate",
})

# ===== Python 流水线 =====
workflow.add_edge("python_generate", "python_execute")
workflow.add_conditional_edges("python_execute", route_after_python_execute, {
    "python_analyze": "python_analyze",
    "python_generate": "python_generate",
    "end": END,
})
workflow.add_edge("python_analyze", "plan_executor")

# ===== 报告生成 → END =====
workflow.add_edge("report_generator", END)

# ===== Human Feedback 路由 =====
workflow.add_conditional_edges("human_feedback", route_after_human_feedback, {
    "plan_executor": "plan_executor",
    "planner": "planner",
    "end": END,
})

# 编译
compiled_workflow = workflow.compile()
logger.info("Workflow compiled: PlanExecutor cycle topology with %d nodes", len(workflow.nodes))
