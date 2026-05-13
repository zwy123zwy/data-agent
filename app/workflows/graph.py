"""
LangGraph 工作流拓扑定义 — 对齐 Java DataAgentConfiguration.nl2sqlGraph

【在系统中的地位】
  本文件是整个后端的"神经网络"——它定义了 16 个节点的连接方式、数据流转路径。
  StateGraph 是 LangGraph 提供的有限状态机框架，包含节点(nodes)和边(edges)。

【模块连接】
  上游 (谁使用这个 graph):
    - streaming_graph_controller.py  → compiled_workflow.astream()  SSE 流式执行
    - graph_controller.py            → compiled_workflow.ainvoke()  同步执行

  中层 (graph 内部调用):
    - workflows/state.py             → WorkflowState 定义 state 类型
    - workflows/nodes/*.py           → 16 个节点函数 (被 add_node 注册)

  下游 (node 输出 → SSE 前端):
    - streaming_graph_controller.py  → 消费 astream 事件，转为 SSE 发送给前端

  Java 对应:
    本文件 = DataAgentConfiguration.java 中的 nl2sqlGraph() 方法
    compiled_workflow = Spring AI 的 CompiledGraph

【核心概念 — 路由函数】
  graph.py 中的每个 route_after_* 函数对应 Java 的 Dispatcher:
    Python                           Java
    ─────────────────────────────────────────────
    route_after_intent()          → IntentRecognitionDispatcher
    route_after_query_rewrite()   → QueryEnhanceDispatcher
    route_after_schema_recall()   → SchemaRecallDispatcher
    route_after_table_relation()  → TableRelationDispatcher (含重试)
    route_after_feasibility()     → FeasibilityAssessmentDispatcher
    route_after_plan_executor()   → PlanExecutorDispatcher (循环调度核心)
    route_after_sql_generate()    → SqlGenerateDispatcher
    route_after_sql_execute()     → SQLExecutorDispatcher
    route_after_python_execute()  → PythonExecutorDispatcher
    route_after_human_feedback()  → HumanFeedbackDispatcher

【重点 — PlanExecutor 循环拓扑】
  这是最复杂的设计: PlanExecutor 不是线性节点，而是一个循环调度器。

  PlanExecutor → 根据 plan_current_step 和 query_plan 决定 next_node:
    - 如果当前步骤是 SQL  → 进入 sql_generate → semantic_consistency → sql_execute → 回到 PlanExecutor
    - 如果当前步骤是 Python → 进入 python_generate → python_execute → python_analyze → 回到 PlanExecutor
    - 如果所有步骤完成      → 进入 report_generator → END
    - 如果需要人工确认      → 进入 human_feedback → (approve/reject) → 回到 PlanExecutor/Planner

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
import asyncio
from typing import Literal
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
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
#
# 【阶段划分】
#   第一阶段 (前置处理): Intent → Knowledge → Rewrite → Schema → Relation → Feasibility → Planner
#     职责: 理解用户意图、召回知识、发现数据库结构、生成执行计划
#     特点: 线性流程，任何节点失败直接 END
#
#   第二阶段 (循环调度): PlanExecutor ←→ {SQL流水线, Python流水线}
#     职责: 逐步执行计划中的每个步骤，SQL 和 Python 交替执行
#     特点: PlanExecutor 是循环中枢，每一步执行完都回到它决定下一步
#
#   第三阶段 (收尾): ReportGenerator → END
#     职责: 汇总所有结果，生成 HTML/Markdown 报告
#     特点: 到达这里意味着所有步骤执行完毕

workflow = StateGraph(WorkflowState)

# 添加所有节点 — 每个节点对应 workflows/nodes/ 下的一个 .py 文件
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

# 入口 — 所有请求都从意图识别开始
workflow.set_entry_point("intent_recognition")

# ===== 第一阶段：前置处理链 =====
# Intent → (data_analysis) → Knowledge → QueryRewrite → Schema → TableRelation → Feasibility → Planner
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
    "table_relation": "table_relation",  # 自循环：重试表关系构建
})
workflow.add_conditional_edges("feasibility", route_after_feasibility, {
    "planner": "planner",
    "end": END,
})

# ===== 第二阶段：Planner → PlanExecutor (进入循环调度) =====
workflow.add_edge("planner", "plan_executor")

# ===== 第三阶段：PlanExecutor 循环调度 =====
# ★ 这是整个拓扑的核心: PlanExecutor 根据当前步骤的 type 决定走哪条流水线
#   每次流水线执行完都会回到 PlanExecutor，形成循环
workflow.add_conditional_edges("plan_executor", route_after_plan_executor, {
    "sql_generate": "sql_generate",
    "python_generate": "python_generate",
    "report_generator": "report_generator",  # 所有步骤完成
    "human_feedback": "human_feedback",       # 需要人工确认
    "planner": "planner",                     # 人工拒绝 → 重新规划
    "end": END,
})

# ===== SQL 流水线 =====
# SqlGenerate → SemanticConsistency → SqlExecute → 回到 PlanExecutor
# 含重试: semantic check 失败 → 重新 sql_generate; execute 失败 → 重新 sql_generate
workflow.add_conditional_edges("sql_generate", route_after_sql_generate, {
    "semantic_consistency": "semantic_consistency",
    "sql_generate": "sql_generate",  # 自循环：SQL 生成失败重试
    "end": END,
})
workflow.add_conditional_edges("semantic_consistency", route_after_semantic_check, {
    "sql_execute": "sql_execute",
    "sql_generate": "sql_generate",  # 语义校验失败 → 重新生成 SQL
})
workflow.add_conditional_edges("sql_execute", route_after_sql_execute, {
    "plan_executor": "plan_executor",  # 成功 → 回到调度器
    "sql_generate": "sql_generate",    # 执行失败 → 重新生成 SQL
})

# ===== Python 流水线 =====
# PythonGenerate → PythonExecute → PythonAnalyze → 回到 PlanExecutor
# 含重试: execute 失败 → 重新 python_generate (最多 N 次后降级)
workflow.add_edge("python_generate", "python_execute")
workflow.add_conditional_edges("python_execute", route_after_python_execute, {
    "python_analyze": "python_analyze",
    "python_generate": "python_generate",  # 执行失败重试
    "end": END,
})
workflow.add_edge("python_analyze", "plan_executor")  # 分析完回到调度器

# ===== 报告生成 → END =====
workflow.add_edge("report_generator", END)

# ===== Human Feedback 路由 =====
# HumanFeedback 节点通过 LangGraph interrupt 机制暂停，等待外部 resume
workflow.add_conditional_edges("human_feedback", route_after_human_feedback, {
    "plan_executor": "plan_executor",  # 批准 → 继续执行
    "planner": "planner",              # 拒绝 → 重新规划
    "end": END,
})

# 编译 — 将声明的拓扑编译为可执行的 LangGraph 状态图
# ★ checkpointer 为 HumanFeedback interrupt/resume 提供状态持久化
# 通过 settings.checkpointer_type 切换:
#   "memory" → MemorySaver (进程重启丢失)
#   "sqlite" → AsyncSqliteSaver (持久化到文件, 跨重启恢复)

async def _build_checkpointer():
    """根据配置创建 checkpointer 实例（异步）"""
    if settings.checkpointer_type == "sqlite":
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
        _ctx = AsyncSqliteSaver.from_conn_string(settings.checkpointer_db_path)
        checkpointer = await _ctx.__aenter__()
        logger.info("Using AsyncSqliteSaver checkpointer: %s", settings.checkpointer_db_path)
        return checkpointer
    else:
        logger.info("Using MemorySaver checkpointer (in-memory)")
        return MemorySaver()

_compiled_workflow = None
_lock = asyncio.Lock()

async def get_compiled_workflow():
    """延迟初始化 compiled_workflow（异步 checkpointer 需要）"""
    global _compiled_workflow
    if _compiled_workflow is not None:
        return _compiled_workflow

    async with _lock:
        if _compiled_workflow is not None:
            return _compiled_workflow

        checkpointer = await _build_checkpointer()
        _compiled_workflow = workflow.compile(checkpointer=checkpointer)
        logger.info("Workflow compiled: PlanExecutor cycle topology with %d nodes", len(workflow.nodes))
        return _compiled_workflow
