"""
计划执行节点（Plan Executor Node）
按步骤执行多步骤计划
"""
from typing import Dict, Any, List
from ..state import AgentState
from .sql_execute import sql_execute_node
from ...core.llm import get_llm_client
import logging

logger = logging.getLogger(__name__)


async def plan_executor_node(state: AgentState) -> Dict[str, Any]:
    """
    计划执行节点

    按顺序执行计划中的每个步骤

    Args:
        state: 工作流状态

    Returns:
        更新后的状态
    """
    query_plan = state.get("query_plan")

    if not query_plan or not query_plan.get("steps"):
        logger.error("[PlanExecutor] No plan to execute")
        return {"error": "No execution plan available"}

    steps = query_plan["steps"]
    logger.info(f"[PlanExecutor] Executing plan with {len(steps)} steps")

    # 存储每个步骤的结果
    step_results = {}

    try:
        for step in steps:
            step_id = step["id"]
            step_type = step["type"]
            description = step.get("description", "")

            logger.info(f"[PlanExecutor] Executing step {step_id}: {description}")

            # 检查依赖
            depends_on = step.get("depends_on", [])
            for dep_id in depends_on:
                if dep_id not in step_results:
                    error_msg = f"Step {step_id} depends on step {dep_id} which hasn't been executed"
                    logger.error(f"[PlanExecutor] {error_msg}")
                    return {"error": error_msg}

            # 根据步骤类型执行
            if step_type == "sql_query":
                result = await execute_sql_step(state, step, step_results)
                step_results[step_id] = result

            elif step_type == "python_analysis":
                result = await execute_python_step(state, step, step_results)
                step_results[step_id] = result

            elif step_type == "report":
                result = await execute_report_step(state, step, step_results)
                step_results[step_id] = result

            else:
                logger.warning(f"[PlanExecutor] Unknown step type: {step_type}")
                step_results[step_id] = {"error": f"Unknown step type: {step_type}"}

        logger.info(f"[PlanExecutor] Plan execution completed")

        # 汇总所有结果
        final_result = {
            "steps_executed": len(steps),
            "step_results": step_results,
            "final_data": step_results.get(steps[-1]["id"])  # 最后一步的结果
        }

        return {
            "plan_execution_result": final_result,
            "sql_result": final_result.get("final_data", {}).get("data")
        }

    except Exception as e:
        logger.error(f"[PlanExecutor] Error: {e}")
        return {"error": f"Plan execution failed: {str(e)}"}


async def execute_sql_step(
    state: AgentState,
    step: Dict[str, Any],
    previous_results: Dict[int, Any]
) -> Dict[str, Any]:
    """执行 SQL 步骤"""
    sql = step.get("sql")
    if not sql:
        return {"error": "No SQL provided"}

    # 创建临时状态执行 SQL
    temp_state = {
        **state,
        "generated_sql": sql
    }

    # 调用 SQL 执行节点
    result = await sql_execute_node(temp_state)

    return {
        "type": "sql_query",
        "sql": sql,
        "data": result.get("sql_result"),
        "error": result.get("sql_error")
    }


async def execute_python_step(
    state: AgentState,
    step: Dict[str, Any],
    previous_results: Dict[int, Any]
) -> Dict[str, Any]:
    """
    执行 Python 分析步骤

    注意: Phase 3 会实现完整的 Python 执行
    目前返回模拟结果
    """
    code = step.get("code", "")
    depends_on = step.get("depends_on", [])

    logger.info(f"[PlanExecutor] Python step - code length: {len(code)}")

    # Phase 3 TODO: 实现真实的 Python 代码执行
    # 目前返回描述性结果
    return {
        "type": "python_analysis",
        "code": code,
        "description": step.get("description"),
        "status": "pending",
        "message": "Python execution will be implemented in Phase 3"
    }


async def execute_report_step(
    state: AgentState,
    step: Dict[str, Any],
    previous_results: Dict[int, Any]
) -> Dict[str, Any]:
    """执行报告生成步骤"""
    depends_on = step.get("depends_on", [])

    # 收集所有依赖步骤的结果
    collected_data = []
    for dep_id in depends_on:
        if dep_id in previous_results:
            collected_data.append(previous_results[dep_id])

    # 生成简单报告
    report = f"执行计划完成\n\n"
    report += f"总共执行了 {len(previous_results)} 个步骤\n\n"

    for step_id, result in previous_results.items():
        step_type = result.get("type", "unknown")
        report += f"步骤 {step_id} ({step_type}):\n"

        if result.get("error"):
            report += f"  错误: {result['error']}\n"
        elif result.get("data"):
            data = result["data"]
            if isinstance(data, list):
                report += f"  返回 {len(data)} 条记录\n"
            else:
                report += f"  执行成功\n"
        report += "\n"

    return {
        "type": "report",
        "report": report,
        "data": collected_data
    }
