"""
Python 分析节点 — 对齐 Java PythonAnalyzeNode

Harness 角色: 调用 LLM 分析 Python 执行结果，生成自然语言分析总结。
降级模式下直接返回基本统计信息。

I/O 契约:
  requires: python_output, python_charts, python_data, user_query
  provides: python_analysis
"""

from typing import Dict, Any
from ..state import WorkflowState, get_canonical_query, get_current_step_number
from ..node_base import WorkflowNode, SSEPayload
from ...core.llm import llm_service
import logging

logger = logging.getLogger(__name__)


class PythonAnalyzeNode(WorkflowNode):
    """Python 分析 — 对齐 Java PythonAnalyzeNode.apply()

    将 Python 代码执行的原始输出转为自然语言分析总结。
    降级模式（python_fallback_mode=True）时跳过 LLM，直接返回统计信息。
    """

    name = "python_analyze"
    description = "分析 Python 执行结果，生成自然语言分析总结"
    requires = ["python_output", "python_charts", "python_data", "user_query"]
    provides = ["python_analysis"]
    applicable_data_sources = ["*"]

    async def execute(self, state: WorkflowState) -> Dict[str, Any]:
        python_output = state.get("python_output")
        python_charts = state.get("python_charts", [])
        python_data = state.get("python_data")
        user_query = get_canonical_query(state)
        fallback_mode = state.get("python_fallback_mode", False)

        if fallback_mode:
            logger.warning("[PythonAnalyze] Fallback mode — Python execution failed after max retries")
            fallback_msg = (
                "Python 代码分析失败（已超过最大重试次数）。"
                "以下报告仅基于 SQL 查询结果生成。"
            )
            sql_result = state.get("sql_result")
            basic_stats = ""
            if sql_result and len(sql_result) > 0:
                basic_stats = f"共查询到 {len(sql_result)} 条记录。"
                cols = list(sql_result[0].keys()) if sql_result else []
                basic_stats += f" 包含字段: {', '.join(cols[:10])}"

            current_step = get_current_step_number(state)
            step_results = dict(state.get("sql_step_results") or {})
            step_results[f"step_{current_step}_analysis"] = fallback_msg + basic_stats

            return {
                "python_analysis": fallback_msg + basic_stats,
                "sql_step_results": step_results,
                "plan_current_step": current_step + 1,
            }

        if not python_output and not python_data:
            logger.warning("[PythonAnalyze] No Python output to analyze")
            return {"python_analysis": "无分析结果"}

        logger.info("[PythonAnalyze] Analyzing Python execution results")

        try:
            prompt = (
                f"用户查询: {user_query}\n\n"
                f"Python 执行输出:\n{python_output or python_data}\n\n"
                f"生成的图表: {', '.join(python_charts) if python_charts else '无'}\n\n"
                f"请根据上述执行结果，生成简洁的分析结论（2-3句话）。\n"
                f"重点说明:\n"
                f"1. 数据的主要特征\n"
                f"2. 关键发现\n"
                f"3. 对用户查询的回答"
            )

            analysis = await llm_service.chat("", prompt, temperature=0.3)
            analysis = analysis.strip()
            logger.info(f"[PythonAnalyze] Analysis: {analysis[:80]}...")

            current_step = get_current_step_number(state)
            step_results = dict(state.get("sql_step_results") or {})
            step_results[f"step_{current_step}_analysis"] = analysis

            return {
                "python_analysis": analysis,
                "sql_step_results": step_results,
                "plan_current_step": current_step + 1,
            }

        except Exception as e:
            logger.error(f"[PythonAnalyze] Error: {e}")
            return {"python_analysis": f"分析失败: {str(e)}"}

    def format_sse(self, output: Dict[str, Any]) -> SSEPayload:
        return SSEPayload(
            text=output.get("python_analysis", "") or "",
            text_type="TEXT",
        )


# LangGraph 兼容实例
python_analyze_node = PythonAnalyzeNode()
