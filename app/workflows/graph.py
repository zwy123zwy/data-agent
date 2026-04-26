"""
工作流图定义 - Phase 3 完整版
包含 Python 分析和报告生成
"""
from typing import Literal
from langgraph.graph import StateGraph, END
from .state import WorkflowState
from .nodes.intent_recognition import intent_recognition_node
from .nodes.knowledge_recall import knowledge_recall_node
from .nodes.query_rewrite import query_rewrite_node
from .nodes.schema_recall import schema_recall_node
from .nodes.sql_generate import sql_generate_node
from .nodes.sql_execute import sql_execute_node
from .nodes.python_generate import python_generate_node
from .nodes.python_execute import python_execute_node
from .nodes.python_analyze import python_analyze_node
from .nodes.report_generator import report_generator_node


def should_continue_after_intent(state: WorkflowState) -> Literal["knowledge_recall", "end"]:
    """判断意图识别后是否继续"""
    intent = state.get("intent")
    if intent == "data_analysis":
        return "knowledge_recall"
    return "end"


def should_retry_sql(state: WorkflowState) -> Literal["sql_generate", "python_generate"]:
    """判断 SQL 执行失败后是否重试"""
    sql_error = state.get("sql_error")
    retry_count = state.get("sql_retry_count", 0)

    # 如果有错误且重试次数小于 3 次，则重试
    if sql_error and retry_count < 3:
        return "sql_generate"
    return "python_generate"


# 创建工作流图
workflow = StateGraph(WorkflowState)

# 添加节点
workflow.add_node("intent_recognition", intent_recognition_node)
workflow.add_node("knowledge_recall", knowledge_recall_node)
workflow.add_node("query_rewrite", query_rewrite_node)
workflow.add_node("schema_recall", schema_recall_node)
workflow.add_node("sql_generate", sql_generate_node)
workflow.add_node("sql_execute", sql_execute_node)
workflow.add_node("python_generate", python_generate_node)
workflow.add_node("python_execute", python_execute_node)
workflow.add_node("python_analyze", python_analyze_node)
workflow.add_node("report_generator", report_generator_node)

# 设置入口点
workflow.set_entry_point("intent_recognition")

# 添加边
workflow.add_conditional_edges(
    "intent_recognition",
    should_continue_after_intent,
    {
        "knowledge_recall": "knowledge_recall",
        "end": END
    }
)

workflow.add_edge("knowledge_recall", "query_rewrite")
workflow.add_edge("query_rewrite", "schema_recall")
workflow.add_edge("schema_recall", "sql_generate")
workflow.add_edge("sql_generate", "sql_execute")

workflow.add_conditional_edges(
    "sql_execute",
    should_retry_sql,
    {
        "sql_generate": "sql_generate",
        "python_generate": "python_generate"
    }
)

workflow.add_edge("python_generate", "python_execute")
workflow.add_edge("python_execute", "python_analyze")
workflow.add_edge("python_analyze", "report_generator")
workflow.add_edge("report_generator", END)

# 编译工作流
compiled_workflow = workflow.compile()
