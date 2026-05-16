"""
可行性评估节点 — 对齐 Java FeasibilityAssessmentNode

Harness 角色: 评估 Schema + Evidence 是否足以支撑用户查询，
防止在信息不足时盲目生成 SQL。不可行时路由到 END。

I/O 契约:
  requires: schema, recalled_knowledge, user_query
  provides: feasibility_result
"""
from typing import Dict, Any
from ..state import WorkflowState, get_canonical_query
from ..node_base import WorkflowNode, SSEPayload
from ...core.llm import llm_service
from ...core.text_utils import clean_code_block
import logging
import json

logger = logging.getLogger(__name__)

FEASIBILITY_SYSTEM_PROMPT = """你是一个查询可行性评估专家。
评估当前可用的数据是否足以回答用户的问题。

评估维度：
1. **Schema 覆盖度**: 数据库中的表和字段是否包含回答问题所需的信息
2. **知识充分性**: 知识库中的业务知识是否足以理解和解答问题
3. **查询复杂度**: 问题是否需要多步分析，当前能力是否支持

返回 JSON 格式：
{
  "feasible": true,
  "reason": "评估说明",
  "missing_info": [],   // 缺失的信息（如果 feasible 为 false）
  "confidence": 0.9      // 置信度 0-1
}
"""


class FeasibilityNode(WorkflowNode):
    """可行性评估 — 对齐 Java FeasibilityAssessmentNode.apply()

    评估 Schema + Evidence 是否足以支撑用户查询。
    不通过时返回 feasible=False → graph.py 路由到 END。
    """

    name = "feasibility"
    description = "评估 Schema + Evidence 是否足以支撑用户查询，防止信息不足时盲目生成 SQL"
    requires = ["schema", "recalled_knowledge", "user_query"]
    provides = ["feasibility_result"]
    applicable_data_sources = ["database"]

    async def execute(self, state: WorkflowState) -> Dict[str, Any]:
        canonical_query = get_canonical_query(state)
        schema = state.get("schema", "")
        evidence = state.get("recalled_knowledge", "")

        logger.info(f"[Feasibility] Assessing query: {canonical_query[:80]}")

        if not schema:
            logger.warning("[Feasibility] No schema available, marking as infeasible")
            return {
                "feasibility_result": {
                    "feasible": False,
                    "reason": "没有可用的数据库 Schema 信息",
                    "missing_info": ["数据库表结构"],
                    "confidence": 0.0,
                }
            }

        try:
            prompt = (
                f"用户问题: {canonical_query}\n\n"
                f"数据库 Schema:\n{schema}\n\n"
                f"已有知识:\n{evidence}\n\n"
                f"请评估以上信息是否足以回答用户问题。"
            )

            text = await llm_service.chat(FEASIBILITY_SYSTEM_PROMPT, prompt, temperature=0.0)
            result = json.loads(clean_code_block(text, lang="json"))

            feasible = result.get("feasible", True)
            reason = result.get("reason", "")
            logger.info(f"[Feasibility] Result: feasible={feasible}, reason={reason[:80]}")

            return {"feasibility_result": result}

        except Exception as e:
            logger.error(f"[Feasibility] Error: {e}")
            # 降级：假定可行
            return {
                "feasibility_result": {
                    "feasible": True,
                    "reason": "评估出错，默认放行",
                    "confidence": 0.5,
                }
            }

    def format_sse(self, output: Dict[str, Any]) -> SSEPayload | None:
        result = output.get("feasibility_result", {})
        if isinstance(result, dict):
            feasible = result.get("feasible", True)
            reason = result.get("reason", "")
            if feasible:
                text = "正在评估查询可行性...可行"
            else:
                text = f"正在评估查询可行性...不可行: {reason}"
        else:
            text = "正在评估查询可行性..."
        return SSEPayload(
            text=text,
            text_type="TEXT",
            metrics_delta={"feasibility_pass": feasible if isinstance(result, dict) else None},
        )


# ========== 路由函数 (供 graph.py 的 conditional_edges 使用) ==========

def route_after_feasibility(state: WorkflowState) -> str:
    """可行性评估后的条件路由 — 对齐 Java FeasibilityAssessmentDispatcher"""
    result = state.get("feasibility_result", {})
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except json.JSONDecodeError:
            return "planner"
    if result.get("feasible", True):
        return "planner"
    return "end"


# LangGraph 兼容实例
feasibility_node = FeasibilityNode()
