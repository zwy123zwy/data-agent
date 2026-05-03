"""
Python 代码执行节点（Python Execute Node） — 对齐 Java PythonExecuteNode
支持执行 + 重试 + 超限降级
"""
from typing import Dict, Any
from ..state import WorkflowState
from ...core.code_executor import get_code_executor
from ...core.config import settings
import logging

logger = logging.getLogger(__name__)


async def python_execute_node(state: WorkflowState) -> Dict[str, Any]:
    """Python 代码执行节点 — 对齐 Java PythonExecuteNode.apply()

    执行 Python 代码，支持:
    - 成功: python_is_success = True, 路由到 python_analyze
    - 失败: python_is_success = False, 路由回 python_generate (重试)
    - 超限: python_fallback_mode = True, 降级到 python_analyze
    """
    python_code = state.get("python_code")
    sql_result = state.get("sql_result")
    tries_count = state.get("python_tries_count", 0) + 1
    max_tries = settings.code_executor.python_max_tries_count

    if not python_code:
        logger.warning("[PythonExecute] No Python code to execute")
        return {
            "python_output": None,
            "python_error": "No Python code available",
            "python_is_success": False,
            "python_tries_count": tries_count,
        }

    logger.info(f"[PythonExecute] Executing (attempt {tries_count}/{max_tries})")

    try:
        executor = get_code_executor(settings.code_executor.executor_type)
        result = await executor.execute(python_code, sql_result)

        if result.success:
            logger.info(f"[PythonExecute] Success, generated {len(result.charts)} charts")
            return {
                "python_output": result.output,
                "python_charts": result.charts,
                "python_data": result.data,
                "python_error": None,
                "python_is_success": True,
                "python_tries_count": tries_count,
            }
        else:
            logger.warning(f"[PythonExecute] Failed (attempt {tries_count}): {result.error}")
            # 如果超过最大重试次数，启用降级模式
            fallback = tries_count >= max_tries
            if fallback:
                logger.warning(f"[PythonExecute] Max retries ({max_tries}) exceeded, enabling fallback mode")

            return {
                "python_output": result.output,
                "python_error": result.error,
                "python_charts": [],
                "python_is_success": False,
                "python_tries_count": tries_count,
                "python_fallback_mode": fallback,
            }

    except Exception as e:
        logger.error(f"[PythonExecute] Exception: {e}")
        fallback = tries_count >= max_tries
        return {
            "python_output": None,
            "python_error": str(e),
            "python_charts": [],
            "python_is_success": False,
            "python_tries_count": tries_count,
            "python_fallback_mode": fallback,
        }
