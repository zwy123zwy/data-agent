"""
计划执行调度节点 — 对齐 Java PlanExecutorNode

【在系统中的地位】
  这是整个 LangGraph 工作流中最核心的节点——循环调度器。
  它不是一次性执行完的节点，而是会被反复进入多次:
    SQL 步骤执行完 → 回到 PlanExecutor → 决定下一步
    Python 步骤执行完 → 回到 PlanExecutor → 决定下一步

【模块连接】
  上游 (谁路由到 PlanExecutor):
    - planner       → 首次进入 (计划刚生成)
    - sql_execute   → SQL 步骤执行完回来 (循环)
    - python_analyze → Python 步骤执行完回来 (循环)
    - human_feedback → 人工审批通过后回来 (循环)

  下游 (PlanExecutor 决定路由到哪):
    - sql_generate     → 当前步骤需要生成 SQL
    - python_generate  → 当前步骤需要生成 Python
    - report_generator → 所有步骤执行完毕
    - human_feedback   → 需要人工确认
    - planner          → 计划校验失败，重新规划

  读取 state:
    - state["query_plan"]           → 执行计划 JSON
    - state["plan_current_step"]    → 当前步骤编号
    - state["human_review_enabled"] → 是否启用人工复核

  写入 state:
    - state["plan_next_node"]       → 决定下一个要执行的节点
    - state["plan_validation_status"] → 计划校验是否通过
    - state["plan_repair_count"]    → 修复尝试次数

  Java 对应:
    plan_executor_node ≈ PlanExecutorNode.java (最复杂的节点)
    route_after_plan_executor ≈ PlanExecutorDispatcher.java

【Plan 结构 (query_plan JSON)】
  {
    "title": "数据分析计划",
    "description": "...",
    "execution_plan": [
      {
        "step": 1,
        "tool_to_use": "SQL_GENERATE_NODE",
        "tool_parameters": {
          "instruction": "查询本月的销售总额"
        }
      },
      {
        "step": 2,
        "tool_to_use": "PYTHON_GENERATE_NODE",
        "tool_parameters": {
          "instruction": "绘制月度销售趋势图"
        }
      },
      {
        "step": 3,
        "tool_to_use": "REPORT_GENERATOR_NODE",
        "tool_parameters": {
          "summary_and_recommendations": "..."
        }
      }
    ]
  }
"""
from typing import Dict, Any, Literal
import json
from ..state import WorkflowState, get_current_step_number
from ...core.config import settings
import logging

logger = logging.getLogger(__name__)

# 支持的节点类型 — 对齐 Java Constant
SQL_GENERATE_NODE = "SQL_GENERATE_NODE"
PYTHON_GENERATE_NODE = "PYTHON_GENERATE_NODE"
REPORT_GENERATOR_NODE = "REPORT_GENERATOR_NODE"
HUMAN_FEEDBACK_NODE = "HUMAN_FEEDBACK_NODE"
SUPPORTED_NODES = {SQL_GENERATE_NODE, PYTHON_GENERATE_NODE, REPORT_GENERATOR_NODE}


def _get_step_params(step: dict) -> dict:
    """兼容新旧 Plan 格式: 获取步骤参数"""
    tp = step.get("tool_parameters") or {}
    return {
        "instruction": tp.get("instruction", step.get("description", "")),
        "sql_query": tp.get("sql_query"),
        "summary_and_recommendations": tp.get("summary_and_recommendations"),
    }


def _validate_plan(plan: dict) -> str | None:
    """校验 Plan 结构有效性 — 对齐 Java PlanExecutorNode.validateExecutionPlanStructure"""
    if not plan:
        return "Validation failed: The plan is empty (null)."
    execution_plan = plan.get("execution_plan") or plan.get("steps", [])
    if not execution_plan:
        return "Validation failed: The generated plan has no execution steps."

    for step in execution_plan:
        tool = step.get("tool_to_use") or step.get("type", "").upper()
        if tool not in SUPPORTED_NODES:
            return f"Validation failed: Plan contains an invalid tool name: '{tool}' in step {step.get('step', step.get('id'))}"

        tp = step.get("tool_parameters") or {}
        params = _get_step_params(step)
        if tool == SQL_GENERATE_NODE and not params["instruction"]:
            return f"Validation failed: SQL generation node is missing description in step {step.get('step', step.get('id'))}"
        if tool == PYTHON_GENERATE_NODE and not params["instruction"]:
            return f"Validation failed: Python generation node is missing instruction in step {step.get('step', step.get('id'))}"
        if tool == REPORT_GENERATOR_NODE and not params["summary_and_recommendations"]:
            return f"Validation failed: Report generation node is missing summary_and_recommendations in step {step.get('step', step.get('id'))}"

    return None  # 校验通过


def _get_execution_steps(plan: dict) -> list:
    """兼容新旧格式：获取执行步骤列表"""
    return plan.get("execution_plan") or plan.get("steps", [])


async def plan_executor_node(state: WorkflowState) -> Dict[str, Any]:
    """计划执行调度节点 — 对齐 Java PlanExecutorNode.apply()

    作为图内的循环调度器：
    1. 校验 Plan 结构
    2. 检查 Human Review 开关
    3. 判断步骤是否全部完成
    4. 路由到下一步执行节点
    """
    # 1. 解析并校验 Plan
    plan_raw = state.get("query_plan")
    if isinstance(plan_raw, str):
        try:
            plan = json.loads(plan_raw)
        except json.JSONDecodeError as e:
            logger.error(f"[PlanExecutor] Plan JSON parse error: {e}")
            return _validation_failed(state, f"Validation failed: The plan is not a valid JSON structure. Error: {e}")
    else:
        plan = plan_raw or {}

    error = _validate_plan(plan)
    if error:
        logger.error(f"[PlanExecutor] Plan validation failed: {error}")
        return _validation_failed(state, error)

    steps = _get_execution_steps(plan)
    logger.info("[PlanExecutor] Plan validation successful.")

    # 2. 检查 Human Review 开关 — 对齐 Java
    human_review_enabled = state.get("human_review_enabled", False)
    is_nl2sql = state.get("is_only_nl2sql", False)
    if human_review_enabled and not is_nl2sql:
        logger.info("[PlanExecutor] Human review enabled: routing to human_feedback node")
        return {
            "plan_validation_status": True,
            "plan_next_node": HUMAN_FEEDBACK_NODE,
        }

    current_step = get_current_step_number(state)
    total_steps = len(steps)

    # 3. 检查是否所有步骤完成
    if current_step > total_steps:
        logger.info(f"[PlanExecutor] All {total_steps} steps completed, routing to report generator")
        return {
            "plan_current_step": 1,  # reset
            "plan_next_node": REPORT_GENERATOR_NODE,
            "plan_validation_status": True,
        }

    # 4. 获取当前步骤并决定下一节点
    step = steps[current_step - 1]
    # 兼容新旧格式
    tool_to_use = step.get("tool_to_use") or step.get("type", "").upper()
    # 旧格式映射
    type_map = {"SQL_QUERY": SQL_GENERATE_NODE, "PYTHON_ANALYSIS": PYTHON_GENERATE_NODE, "REPORT": REPORT_GENERATOR_NODE}
    tool_to_use = type_map.get(tool_to_use, tool_to_use)

    logger.info(f"[PlanExecutor] Step {current_step}/{total_steps} → {tool_to_use}")
    return {
        "plan_next_node": tool_to_use,
        "plan_validation_status": True,
    }


def _validation_failed(state: WorkflowState, error: str) -> Dict[str, Any]:
    """校验失败处理 — 对齐 Java PlanExecutorNode.buildValidationResult"""
    repair_count = state.get("plan_repair_count", 0)
    return {
        "plan_validation_status": False,
        "plan_validation_error": error,
        "plan_repair_count": repair_count + 1,
    }


# ========== 路由函数 (供 graph.py 的 conditional_edges 使用) ==========

MAX_REPAIR_ATTEMPTS = 3

def route_after_plan_executor(state: WorkflowState) -> Literal[
    "sql_generate", "python_generate", "report_generator", "human_feedback", "planner", "end"
]:
    """PlanExecutor 后的条件路由 — 对齐 Java PlanExecutorDispatcher"""
    validation_passed = state.get("plan_validation_status", False)

    if not validation_passed:
        repair_count = state.get("plan_repair_count", 0)
        if repair_count > MAX_REPAIR_ATTEMPTS:
            logger.error(f"[PlanExecutor] Plan repair attempts exceeded {MAX_REPAIR_ATTEMPTS}, ending")
            return "end"
        logger.warning(f"[PlanExecutor] Validation failed, routing to planner for repair (attempt {repair_count})")
        return "planner"

    next_node = state.get("plan_next_node", "")

    node_map = {
        SQL_GENERATE_NODE: "sql_generate",
        PYTHON_GENERATE_NODE: "python_generate",
        REPORT_GENERATOR_NODE: "report_generator",
        HUMAN_FEEDBACK_NODE: "human_feedback",
    }
    if next_node in node_map:
        return node_map[next_node]

    # 旧格式兼容
    old_map = {"sql_query": "sql_generate", "python_analysis": "python_generate", "report": "report_generator"}
    if next_node.lower() in old_map:
        return old_map[next_node.lower()]

    logger.warning(f"[PlanExecutor] Unknown next node: {next_node}, defaulting to report_generator")
    return "report_generator"
