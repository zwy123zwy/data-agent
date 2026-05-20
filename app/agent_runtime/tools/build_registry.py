# [阶段2] 构建完整 12 Tool 注册表

from __future__ import annotations

from app.agent_runtime.tools.base import BaseTool
from app.agent_runtime.tools.execute_sql import ExecuteSqlTool
from app.agent_runtime.tools.generate_sql import GenerateSqlTool
from app.agent_runtime.tools.registry import ToolRegistry
from app.agent_runtime.tools.search_knowledge import SearchKnowledgeTool
from app.agent_runtime.tools.wrap_v1_node import V1NodeTool
from app.workflows.nodes.human_feedback_node import human_feedback_node
from app.workflows.nodes.python_analyze import python_analyze_node
from app.workflows.nodes.python_execute import python_execute_node
from app.workflows.nodes.python_generate import python_generate_node
from app.workflows.nodes.query_rewrite import query_rewrite_node
from app.workflows.nodes.report_generator import report_generator_node
from app.workflows.nodes.schema_recall import schema_recall_node
from app.workflows.nodes.semantic_consistency import semantic_consistency_node
from app.workflows.nodes.table_relation import table_relation_node


def build_full_registry() -> ToolRegistry:
    """[阶段2] 注册 12/12 Tool。"""
    registry = ToolRegistry()
    tools: list[BaseTool] = [
        SearchKnowledgeTool(),
        V1NodeTool("rewrite_query", query_rewrite_node, "Explorer"),
        V1NodeTool("inspect_schema", schema_recall_node, "Explorer", "schema"),
        V1NodeTool("discover_relations", table_relation_node, "Explorer"),
        V1NodeTool("validate_sql", semantic_consistency_node, "Explorer"),
        GenerateSqlTool(),
        ExecuteSqlTool(),
        V1NodeTool("generate_python", python_generate_node, "Insight"),
        V1NodeTool("execute_python", python_execute_node, "Insight"),
        V1NodeTool("analyze_result", python_analyze_node, "Insight"),
        V1NodeTool(
            "generate_report",
            report_generator_node,
            "Reporter",
            None,
            summary_fn=lambda o: (
                "报告生成完成"
                if o.get("html_report") or o.get("markdown_report")
                else "报告步骤完成"
            ),
        ),
        V1NodeTool("ask_human", human_feedback_node, "Explorer", summary_fn=lambda _: "等待人工确认"),
    ]
    for t in tools:
        registry.register(t)
    return registry
