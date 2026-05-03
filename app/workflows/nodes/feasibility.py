"""
可行性评估节点（Feasibility Assessment Node） — 对齐 Java FeasibilityAssessmentNode
评估 Schema + Evidence 是否足以支撑用户查询
"""
from typing import Dict, Any
from ..state import WorkflowState, get_canonical_query
from ...core.llm import get_llm_client
from ...core.config import settings
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


async def feasibility_node(state: WorkflowState) -> Dict[str, Any]:
    """可行性评估节点 — 对齐 Java FeasibilityAssessmentNode.apply()"""
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
        llm = get_llm_client()
        prompt = (
            f"用户问题: {canonical_query}\n\n"
            f"数据库 Schema:\n{schema}\n\n"
            f"已有知识:\n{evidence}\n\n"
            f"请评估以上信息是否足以回答用户问题。"
        )

        response = await llm.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": FEASIBILITY_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
        )

        text = response.choices[0].message.content.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if text.startswith("```json") else text[3:]
            text = text.rsplit("```", 1)[0]
        result = json.loads(text)

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


def route_after_feasibility(state: WorkflowState) -> str:
    """可行性评估后的条件路由"""
    result = state.get("feasibility_result", {})
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except json.JSONDecodeError:
            return "planner"
    if result.get("feasible", True):
        return "planner"
    return "end"
