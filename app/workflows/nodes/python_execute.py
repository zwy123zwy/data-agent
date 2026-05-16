"""
Python 代码执行节点 — 对齐 Java PythonExecuteNode

Harness 角色: 实际执行 LLM 生成的 Python 代码。
将 SQL 结果注入后运行，支持失败重试和降级模式。

I/O 契约:
  requires: python_code, sql_result, python_tries_count
  provides: python_output, python_charts, python_data, python_is_success,
            python_tries_count, python_fallback_mode
"""

from typing import Dict, Any
from ..state import WorkflowState
from ..node_base import WorkflowNode, SSEPayload
from ...core.code_executor import get_code_executor
from ...core.config import settings
import logging

logger = logging.getLogger(__name__)


class PythonExecuteNode(WorkflowNode):
    """Python 代码执行 — 对齐 Java PythonExecuteNode.apply()

    执行 LLM 生成的 Python 代码，注入 SQL 结果作为数据。
    成功 → 路由到 python_analyze
    失败 → 路由回 python_generate（重试）或降级到 python_analyze
    """

    name = "python_execute"
    description = "在沙箱中执行 LLM 生成的 Python 代码"
    requires = ["python_code", "sql_result", "python_tries_count"]
    provides = [
        "python_output", "python_charts", "python_data",
        "python_is_success", "python_tries_count", "python_fallback_mode",
    ]
    applicable_data_sources = ["*"]

    async def execute(self, state: WorkflowState) -> Dict[str, Any]:
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
                fallback = tries_count >= max_tries
                if fallback:
                    logger.warning(
                        f"[PythonExecute] Max retries ({max_tries}) exceeded, enabling fallback mode"
                    )
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

    def format_sse(self, output: Dict[str, Any]) -> SSEPayload:
        is_success = output.get("python_is_success", False)
        if is_success:
            return SSEPayload(
                text="Python 代码执行成功",
                text_type="TEXT",
                metrics_delta={"python_executed": True, "python_success": True},
            )
        error = output.get("python_error", "")
        return SSEPayload(
            text=f"Python 代码执行失败: {error[:200]}" if error else "Python 代码执行中...",
            text_type="TEXT",
            metrics_delta={"python_executed": True, "python_success": False},
        )


# LangGraph 兼容实例
python_execute_node = PythonExecuteNode()
