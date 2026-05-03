"""
Python 代码执行节点 — 对齐 Java PythonExecuteNode

【在系统中的地位】
  这个节点实际执行 LLM 生成的 Python 代码。它将 SQL 查询结果作为数据注入，
  运行代码生成分析输出和图表。支持失败重试和降级模式。

【模块连接】
  上游 (由谁路由到此):
    - python_generate → LLM 生成代码后无条件进入此节点

  下游 (写入 state):
    - state["python_output"]    → 标准输出 (print 内容)
    - state["python_error"]     → 错误信息 (如果失败)
    - state["python_charts"]    → 生成的图表文件路径列表
    - state["python_data"]      → 返回的结构化数据
    - state["python_is_success"] → 执行是否成功
    - state["python_tries_count"] → 当前尝试次数
    - state["python_fallback_mode"] → 是否进入降级模式

  调用:
    - core/code_executor.py:get_code_executor() → 获取执行器 (local/docker/ai-sim)

  路由 (graph.py route_after_python_execute):
    - 成功 → python_analyze (分析执行结果)
    - 失败且未超限 → python_generate (重新生成代码)
    - 失败且超限 → python_analyze (降级: 即使失败也继续分析)

  Java 对应:
    python_execute_node ≈ PythonExecuteNode.java

【数据注入机制】
  SQL 查询结果 (sql_result) 作为变量注入到 Python 代码中:
    code = "import json\nsql_result = json.load(...)\n" + llm_generated_code
  这样 LLM 只需要假设 sql_result 变量存在即可。
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
