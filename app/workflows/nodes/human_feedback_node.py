"""
人工反馈节点 — 对齐 Java HumanFeedbackNode

【在系统中的地位】
  这是 Human-in-the-Loop 的核心节点。它使用 LangGraph 的 interrupt() 机制
  在图执行中途暂停，等待用户在界面上审批或拒绝执行计划。

【模块连接】
  上游 (由谁路由到此):
    - plan_executor → human_review_enabled=True 时路由而来

  下游 (写入 state):
    - state["human_feedback_data"] → 用户反馈内容 (action + reason)
    - state["human_next_node"]     → 审批通过 → plan_executor / 拒绝 → planner
    - state["plan_repair_count"]   → 拒绝次数 (超过 MAX_REJECT_COUNT 则终止)

  调用链:
    - LangGraph interrupt() → 暂停图执行
    - 前端通过 SSE event:paused 收到通知
    - 用户审批后，前端再次调用 /api/stream/search?threadId=...
    - Command(resume={...}) 恢复执行，feedback 值返回给 interrupt() 的调用处

  路由 (graph.py route_after_human_feedback):
    - approve → plan_executor (继续执行后续步骤)
    - reject  → planner (重新生成计划)
    - reject(超限) → END (拒绝次数太多，终止)

  Java 对应:
    human_feedback_node ≈ HumanFeedbackNode.java
    interrupt()         ≈ CompiledGraph.interruptBefore(HUMAN_FEEDBACK_NODE)
"""
from typing import Dict, Any, Literal
from langgraph.types import interrupt
from ..state import WorkflowState, get_current_step_number
import logging
import json

logger = logging.getLogger(__name__)

# 对齐 Java Constant 的节点名称
SQL_GENERATE_NODE = "SQL_GENERATE_NODE"
PYTHON_GENERATE_NODE = "PYTHON_GENERATE_NODE"
REPORT_GENERATOR_NODE = "REPORT_GENERATOR_NODE"

MAX_REJECT_COUNT = 3


def _describe_plan_for_review(state: WorkflowState) -> str:
    """生成供人工复核的 Plan 描述文本 — 对齐 Java HumanFeedbackNode"""
    plan = state.get("query_plan")
    if isinstance(plan, str):
        try:
            plan = json.loads(plan)
        except json.JSONDecodeError:
            plan = {}
    steps = plan.get("execution_plan") or plan.get("steps", [])
    thought = plan.get("thought_process", "")

    lines = [
        f"## 分析思路\n{thought}\n",
        f"## 执行计划 ({len(steps)} 步)\n",
    ]
    for s in steps:
        step_num = s.get("step", s.get("id", "?"))
        tool = s.get("tool_to_use") or s.get("type", "")
        params = s.get("tool_parameters") or {}
        instruction = params.get("instruction", s.get("description", ""))
        lines.append(f"- **Step {step_num}** [{tool}]: {instruction}")

    return "\n".join(lines)


async def human_feedback_node(state: WorkflowState) -> Dict[str, Any]:
    """人工反馈节点 — 对齐 Java HumanFeedbackNode.apply()

    使用 LangGraph interrupt() 暂停图执行，等待外部审批:
    - 批准: human_feedback_data = {"action": "approve"}
    - 拒绝: human_feedback_data = {"action": "reject", "reason": "..."}

    外部通过 Command(resume=...) 恢复执行。
    """
    plan_desc = _describe_plan_for_review(state)
    current_step = get_current_step_number(state)
    reject_count = state.get("plan_repair_count", 0)

    logger.info(f"[HumanFeedback] Pausing for review (reject count: {reject_count}/{MAX_REJECT_COUNT})")

    # LangGraph interrupt — 图在此暂停，等待外部 resume
    feedback = interrupt({
        "type": "human_feedback",
        "message": "请审核执行计划",
        "plan_description": plan_desc,
        "current_step": current_step,
        "reject_count": reject_count,
    })

    logger.info(f"[HumanFeedback] Received feedback: {feedback}")

    if not feedback:
        logger.warning("[HumanFeedback] No feedback provided, defaulting to approve")
        return {
            "human_feedback_data": {"action": "approve"},
            "human_next_node": "plan_executor",
        }

    action = feedback.get("action", "approve")

    if action == "approve":
        logger.info("[HumanFeedback] Plan approved, routing to PlanExecutor")
        return {
            "human_feedback_data": feedback,
            "human_next_node": "plan_executor",
            "plan_validation_status": True,
        }
    else:
        reason = feedback.get("reason", "用户拒绝执行计划")
        new_reject_count = reject_count + 1
        logger.warning(f"[HumanFeedback] Plan rejected (count {new_reject_count}): {reason}")

        if new_reject_count >= MAX_REJECT_COUNT:
            logger.error(f"[HumanFeedback] Max reject count ({MAX_REJECT_COUNT}) exceeded, ending")
            return {
                "human_feedback_data": feedback,
                "plan_repair_count": new_reject_count,
                "plan_validation_status": False,
                "plan_validation_error": f"Rejected {new_reject_count} times. Final reason: {reason}",
                "human_next_node": "end",
            }

        return {
            "human_feedback_data": feedback,
            "plan_repair_count": new_reject_count,
            "plan_validation_status": False,
            "plan_validation_error": reason,
            "human_next_node": "planner",
        }


# ========== 路由函数 ==========

def route_after_human_feedback(state: WorkflowState) -> Literal["plan_executor", "planner", "end"]:
    """HumanFeedback 后的条件路由 — 对齐 Java HumanFeedbackDispatcher"""
    next_node = state.get("human_next_node", "plan_executor")

    node_map = {
        "plan_executor": "plan_executor",
        "planner": "planner",
        "end": "end",
    }
    return node_map.get(next_node, "plan_executor")
