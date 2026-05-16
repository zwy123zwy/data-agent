"""
计划执行调度节点 — 对齐 Java PlanExecutorNode

Harness 角色: LangGraph 工作流的核心循环调度器。不是一次性节点，而是被反复进入：
SQL/Python 步骤完成后回到此节点决定下一步。负责 Plan 校验、Human Review 开关、
步骤推进和路由决策。

I/O 契约:
  requires: query_plan, plan_current_step
  provides: plan_next_node, plan_validation_status, plan_repair_count
"""
from typing import Dict, Any, Literal
import json
from ..state import WorkflowState, get_current_step_number
from ..node_base import WorkflowNode, SSEPayload
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
            return (
                f"Validation failed: Plan contains an invalid tool name: '{tool}' "
                f"in step {step.get('step', step.get('id'))}"
            )

        tp = step.get("tool_parameters") or {}
        params = _get_step_params(step)
        if tool == SQL_GENERATE_NODE and not params["instruction"]:
            return (
                f"Validation failed: SQL generation node is missing description "
                f"in step {step.get('step', step.get('id'))}"
            )
        if tool == PYTHON_GENERATE_NODE and not params["instruction"]:
            return (
                f"Validation failed: Python generation node is missing instruction "
                f"in step {step.get('step', step.get('id'))}"
            )
        if tool == REPORT_GENERATOR_NODE and not params["summary_and_recommendations"]:
            return (
                f"Validation failed: Report generation node is missing "
                f"summary_and_recommendations in step {step.get('step', step.get('id'))}"
            )

    return None  # 校验通过


def _get_execution_steps(plan: dict) -> list:
    """兼容新旧格式：获取执行步骤列表"""
    return plan.get("execution_plan") or plan.get("steps", [])


class PlanExecutorNode(WorkflowNode):
    """计划执行调度 — 对齐 Java PlanExecutorNode.apply()

    图内循环调度器，职责:
    1. 校验 Plan 结构（不合法则回 planner 修复）
    2. 检查 Human Review 开关（开启则路由到 human_feedback）
    3. 判断步骤是否全部完成（完成则路由到 report_generator 或 END）
    4. 根据当前步骤的 tool_to_use 路由到对应执行节点

    注意: plan_current_step 由各流水线末端节点递增：
      - SQL 流水线: sql_execute 递增
      - Python 流水线: python_analyze 递增
    """

    name = "plan_executor"
    description = "核心循环调度器 — Plan 校验、Human Review 开关、步骤推进、路由决策"
    requires = ["query_plan", "plan_current_step"]
    provides = ["plan_next_node", "plan_validation_status", "plan_repair_count"]
    applicable_data_sources = ["*"]

    async def execute(self, state: WorkflowState) -> Dict[str, Any]:
        # 1. 解析并校验 Plan
        plan_raw = state.get("query_plan")
        if isinstance(plan_raw, str):
            try:
                plan = json.loads(plan_raw)
            except json.JSONDecodeError as e:
                logger.error(f"[PlanExecutor] Plan JSON parse error: {e}")
                return _validation_failed(
                    state,
                    f"Validation failed: The plan is not a valid JSON structure. Error: {e}"
                )
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
            if is_nl2sql:
                logger.info(
                    f"[PlanExecutor] All {total_steps} steps completed (NL2SQL only, ending)"
                )
                return {
                    "plan_current_step": 1,
                    "plan_next_node": "END",
                    "plan_validation_status": True,
                }
            logger.info(
                f"[PlanExecutor] All {total_steps} steps completed, routing to report generator"
            )
            return {
                "plan_current_step": 1,  # reset
                "plan_next_node": REPORT_GENERATOR_NODE,
                "plan_validation_status": True,
            }

        # 4. 获取当前步骤并决定下一节点
        step = steps[current_step - 1]
        tool_to_use = step.get("tool_to_use") or step.get("type", "").upper()
        # 旧格式映射
        type_map = {
            "SQL_QUERY": SQL_GENERATE_NODE,
            "PYTHON_ANALYSIS": PYTHON_GENERATE_NODE,
            "REPORT": REPORT_GENERATOR_NODE,
        }
        tool_to_use = type_map.get(tool_to_use, tool_to_use)

        logger.info(f"[PlanExecutor] Step {current_step}/{total_steps} → {tool_to_use}")
        return {
            "plan_next_node": tool_to_use,
            "plan_validation_status": True,
        }

    def format_sse(self, output: Dict[str, Any]) -> SSEPayload | None:
        next_node = output.get("plan_next_node", "")
        current_step = output.get("plan_current_step", 1)
        if next_node:
            text = f"正在执行步骤 {current_step}..."
        else:
            text = "正在执行计划..."
        return SSEPayload(text=text, text_type="TEXT")


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
            logger.error(
                f"[PlanExecutor] Plan repair attempts exceeded {MAX_REPAIR_ATTEMPTS}, ending"
            )
            return "end"
        logger.warning(
            f"[PlanExecutor] Validation failed, routing to planner for repair "
            f"(attempt {repair_count})"
        )
        return "planner"

    next_node = state.get("plan_next_node", "")

    # 对齐 Java: isOnlyNl2Sql 模式完成时直接 END
    if next_node == "END":
        return "end"

    node_map = {
        SQL_GENERATE_NODE: "sql_generate",
        PYTHON_GENERATE_NODE: "python_generate",
        REPORT_GENERATOR_NODE: "report_generator",
        HUMAN_FEEDBACK_NODE: "human_feedback",
    }
    if next_node in node_map:
        return node_map[next_node]

    # 旧格式兼容
    old_map = {
        "sql_query": "sql_generate",
        "python_analysis": "python_generate",
        "report": "report_generator",
    }
    if next_node.lower() in old_map:
        return old_map[next_node.lower()]

    logger.warning(
        f"[PlanExecutor] Unknown next node: {next_node}, defaulting to report_generator"
    )
    return "report_generator"


# LangGraph 兼容实例
plan_executor_node = PlanExecutorNode()
