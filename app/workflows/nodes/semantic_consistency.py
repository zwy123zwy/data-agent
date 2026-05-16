"""
语义一致性校验节点 — 对齐 Java SemanticConsistencyNode

Harness 角色: 校验 LLM 生成的 SQL 与原始问题在语义上是否一致，
防止 SQL 幻觉（查错表、漏条件等）。不通过时路由回 sql_generate 重试。

I/O 契约:
  requires: generated_sql, schema, user_query, recalled_knowledge, db_dialect_type
  provides: semantic_consistency_result, sql_regenerate_reason
"""

from typing import Dict, Any
from ..state import WorkflowState, get_canonical_query, get_current_instruction
from ..node_base import WorkflowNode, SSEPayload
from ...core.llm import llm_service
import logging

logger = logging.getLogger(__name__)

SEMANTIC_CHECK_SYSTEM_PROMPT = """你是一个 SQL 语义一致性校验专家。
检查生成的 SQL 语句是否与用户的查询意图和描述一致。

校验规则：
1. SQL 涉及的表和字段是否存在于 Schema 中
2. SQL 中的过滤条件
3. SQL 的计算逻辑是否正确（聚合、排序、分组等）
4. 是否有多余或遗漏的查询条件
5. JOIN 关系是否正确

返回：
- 如果通过：返回 "通过: <简要说明>"
- 如果不通过：返回 "不通过: <详细说明问题>"
"""


class SemanticConsistencyNode(WorkflowNode):
    """语义一致性校验 — 对齐 Java SemanticConsistencyNode.apply()

    防止 LLM 生成的 SQL 答非所问。不通过时写入 sql_regenerate_reason，
    路由层据此回到 sql_generate 重试。
    """

    name = "semantic_consistency"
    description = "校验 SQL 语义是否与用户意图一致，防止 SQL 幻觉"
    requires = ["generated_sql", "schema", "user_query", "recalled_knowledge", "db_dialect_type"]
    provides = ["semantic_consistency_result", "sql_regenerate_reason"]
    applicable_data_sources = ["database"]

    async def execute(self, state: WorkflowState) -> Dict[str, Any]:
        sql = state.get("generated_sql", "")

        if not sql:
            logger.warning("[SemanticConsistency] No SQL to validate")
            return {"semantic_consistency_result": True}

        logger.info(f"[SemanticConsistency] Validating SQL: {sql[:100]}...")

        try:
            schema = state.get("schema", "")
            evidence = state.get("recalled_knowledge", "")
            dialect = state.get("db_dialect_type", "")
            user_query = get_canonical_query(state)
            instruction = get_current_instruction(state)

            prompt = (
                f"用户查询: {user_query}\n\n"
                f"当前步骤需求: {instruction}\n\n"
                f"数据库方言: {dialect}\n\n"
                f"数据库 Schema:\n{schema}\n\n"
                f"知识证据:\n{evidence}\n\n"
                f"待校验 SQL:\n{sql}\n\n"
                f"请校验以上 SQL 的语义一致性。"
            )

            validation_result = await llm_service.chat(SEMANTIC_CHECK_SYSTEM_PROMPT, prompt, temperature=0.0)
            validation_result = validation_result.strip()
            is_passed = not validation_result.startswith("不通过")

            logger.info(
                f"[SemanticConsistency] Result: passed={is_passed}, detail={validation_result[:80]}"
            )

            if is_passed:
                return {"semantic_consistency_result": True}
            else:
                return {
                    "semantic_consistency_result": False,
                    "sql_regenerate_reason": {
                        "type": "semantic",
                        "reason": validation_result,
                    },
                }

        except Exception as e:
            logger.error(f"[SemanticConsistency] Error: {e}")
            return {"semantic_consistency_result": True}

    def format_sse(self, output: Dict[str, Any]) -> SSEPayload:
        passed = output.get("semantic_consistency_result", False)
        return SSEPayload(
            text="正在校验 SQL 语义...\u2713 通过" if passed else "正在校验 SQL 语义...\u26a0 未通过",
            text_type="TEXT",
            metrics_delta={"sql_semantic_pass": passed},
        )


# LangGraph 兼容实例
semantic_consistency_node = SemanticConsistencyNode()
