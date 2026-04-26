"""
Python 代码执行节点（Python Execute Node）
执行 Python 分析代码
"""
from typing import Dict, Any
from ..state import AgentState
from ...core.code_executor import get_code_executor
import logging

logger = logging.getLogger(__name__)


async def python_execute_node(state: AgentState) -> Dict[str, Any]:
    """
    Python 代码执行节点

    执行生成的 Python 代码

    Args:
        state: 工作流状态

    Returns:
        更新后的状态
    """
    python_code = state.get("python_code")
    sql_result = state.get("sql_result")

    if not python_code:
        logger.warning("[PythonExecute] No Python code to execute")
        return {"python_output": None, "python_error": "No Python code available"}

    logger.info("[PythonExecute] Executing Python code")

    try:
        # 获取执行器（默认使用 local，可配置为 ai-sim）
        executor = get_code_executor("ai-sim")  # 使用 AI 模拟执行（安全）

        # 执行代码
        result = await executor.execute(python_code, sql_result)

        if result.success:
            logger.info(f"[PythonExecute] Execution successful, generated {len(result.charts)} charts")
            return {
                "python_output": result.output,
                "python_charts": result.charts,
                "python_data": result.data,
                "python_error": None
            }
        else:
            logger.error(f"[PythonExecute] Execution failed: {result.error}")
            return {
                "python_output": result.output,
                "python_error": result.error,
                "python_charts": []
            }

    except Exception as e:
        logger.error(f"[PythonExecute] Error: {e}")
        return {
            "python_output": None,
            "python_error": str(e),
            "python_charts": []
        }
