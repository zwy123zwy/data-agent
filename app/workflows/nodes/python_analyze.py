"""
Python 分析节点（Python Analyze Node） — 对齐 Java PythonAnalyzeNode
分析执行结果，处理降级模式，回写步骤结果
"""
from typing import Dict, Any
from ..state import WorkflowState, get_canonical_query, get_current_step_number
from ...core.llm import get_llm_client
from ...core.config import settings
import logging

logger = logging.getLogger(__name__)


async def python_analyze_node(state: WorkflowState) -> Dict[str, Any]:
    """Python 分析节点 — 对齐 Java PythonAnalyzeNode.apply()

    1. 检测 python_fallback_mode → 返回降级提示
    2. LLM 分析 Python 执行结果，生成分析结论
    3. 回写结果到 sql_execute_node_output (按步骤)
    """
    python_output = state.get("python_output")
    python_charts = state.get("python_charts", [])
    python_data = state.get("python_data")
    user_query = get_canonical_query(state)
    fallback_mode = state.get("python_fallback_mode", False)

    # 降级模式处理 — 对齐 Java PythonAnalyzeNode
    if fallback_mode:
        logger.warning("[PythonAnalyze] Fallback mode active — Python execution failed after max retries")
        fallback_msg = (
            "Python 代码分析失败（已超过最大重试次数）。"
            "以下报告仅基于 SQL 查询结果生成。"
        )
        # 尝试提供基本的统计信息
        sql_result = state.get("sql_result")
        basic_stats = ""
        if sql_result and len(sql_result) > 0:
            basic_stats = f"共查询到 {len(sql_result)} 条记录。"
            if len(sql_result) > 0:
                cols = list(sql_result[0].keys())
                basic_stats += f" 包含字段: {', '.join(cols[:10])}"

        current_step = get_current_step_number(state)
        step_results = dict(state.get("sql_step_results") or {})
        step_results[f"step_{current_step}_analysis"] = fallback_msg + basic_stats

        return {
            "python_analysis": fallback_msg + basic_stats,
            "sql_step_results": step_results,
        }

    # 正常分析模式
    if not python_output and not python_data:
        logger.warning("[PythonAnalyze] No Python output to analyze")
        return {"python_analysis": "无分析结果"}

    logger.info("[PythonAnalyze] Analyzing Python execution results")

    try:
        llm = get_llm_client()

        prompt = (
            f"用户查询: {user_query}\n\n"
            f"Python 执行输出:\n{python_output or python_data}\n\n"
            f"生成的图表: {', '.join(python_charts) if python_charts else '无'}\n\n"
            f"请根据上述执行结果，生成简洁的分析结论（2-3句话）。\n"
            f"重点说明:\n"
            f"1. 数据的主要特征\n"
            f"2. 关键发现\n"
            f"3. 对用户查询的回答\n\n"
            f"只返回分析文字，不要有标题或格式。"
        )

        response = await llm.chat.completions.create(
            model=settings.openai_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )

        analysis = response.choices[0].message.content.strip()
        logger.info(f"[PythonAnalyze] Analysis: {analysis[:80]}...")

        # 回写步骤分析结果 — 对齐 Java
        current_step = get_current_step_number(state)
        step_results = dict(state.get("sql_step_results") or {})
        step_results[f"step_{current_step}_analysis"] = analysis

        return {
            "python_analysis": analysis,
            "sql_step_results": step_results,
        }

    except Exception as e:
        logger.error(f"[PythonAnalyze] Error: {e}")
        return {"python_analysis": f"分析失败: {str(e)}"}
