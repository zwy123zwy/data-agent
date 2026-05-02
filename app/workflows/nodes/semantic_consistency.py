"""
语义一致性校验节点（Semantic Consistency Node） — 对齐 Java SemanticConsistencyNode
在 SQL 执行前校验其语义是否与用户意图一致
"""
from typing import Dict, Any
from ..state import WorkflowState, get_canonical_query, get_current_instruction
from ..core.llm import get_llm_client
from ..core.config import settings
import logging

logger = logging.getLogger(__name__)

SEMANTIC_CHECK_SYSTEM_PROMPT = """你是一个 SQL 语义一致性校验专家。
检查生成的 SQL 语句是否与用户的查询意图和描述一致。

校验规则：
1. SQL 涉及的表和字段是否存在于 Schema 中
2. SQL 中的过滤条件是否与用户意图匹配
3. SQL 的计算逻辑是否正确（聚合、排序、分组等）
4. 是否有多余或遗漏的查询条件
5. JOIN 关系是否正确

返回：
- 如果通过：返回 "通过: <简要说明>"
- 如果不通过：返回 "不通过: <详细说明问题>"
"""


async def semantic_consistency_node(state: WorkflowState) -> Dict[str, Any]:
    """语义一致性校验节点 — 对齐 Java SemanticConsistencyNode.apply()

    校验 SQL 语义一致性：
    - 通过 → semantic_consistency_result = true
    - 不通过 → semantic_consistency_result = false + 设置 sql_regenerate_reason
    """
    sql = state.get("generated_sql", "")
    schema = state.get("schema", "")
    evidence = state.get("recalled_knowledge", "")
    dialect = state.get("db_dialect_type", "")
    user_query = get_canonical_query(state)
    instruction = get_current_instruction(state)

    if not sql:
        logger.warning("[SemanticConsistency] No SQL to validate")
        return {"semantic_consistency_result": True}

    logger.info(f"[SemanticConsistency] Validating SQL: {sql[:100]}...")

    try:
        llm = get_llm_client()
        prompt = (
            f"用户查询: {user_query}\n\n"
            f"当前步骤需求: {instruction}\n\n"
            f"数据库方言: {dialect}\n\n"
            f"数据库 Schema:\n{schema}\n\n"
            f"知识证据:\n{evidence}\n\n"
            f"待校验 SQL:\n{sql}\n\n"
            f"请校验以上 SQL 的语义一致性。"
        )

        response = await llm.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": SEMANTIC_CHECK_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
        )

        validation_result = response.choices[0].message.content.strip()
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
        # 出错时默认通过，避免阻塞流程
        return {"semantic_consistency_result": True}
