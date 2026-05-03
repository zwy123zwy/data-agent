"""
查询改写节点（Query Rewrite Node） — 对齐 Java QueryEnhanceNode
基于知识库改写用户查询，将业务术语映射为技术术语
"""
from typing import Dict, Any
from ..state import WorkflowState
from ...core.llm import llm_service
import logging

logger = logging.getLogger(__name__)


QUERY_REWRITE_SYSTEM_PROMPT = """你是一个查询改写助手。根据提供的业务知识，将用户的业务查询改写为更精确的技术查询。

改写规则：
1. 将业务术语替换为对应的技术术语或字段名
2. 补充必要的业务规则和约束条件
3. 保持查询的原始意图不变
4. 如果知识中没有相关信息，保持原查询不变

只返回改写后的查询，不要解释。"""


async def query_rewrite_node(state: WorkflowState) -> Dict[str, Any]:
    """查询改写节点 — 对齐 Java QueryEnhanceNode.apply()"""
    user_query = state["user_query"]
    recalled_knowledge = state.get("recalled_knowledge", "")

    logger.info(f"[QueryRewrite] Rewriting query: {user_query}")

    if not recalled_knowledge:
        logger.info("[QueryRewrite] No knowledge recalled, using original query")
        return {"rewritten_query": user_query}

    try:
        user_prompt = f"{recalled_knowledge}\n\n用户查询: {user_query}"
        rewritten_query = await llm_service.chat(QUERY_REWRITE_SYSTEM_PROMPT, user_prompt)
        rewritten_query = rewritten_query.strip()

        logger.info(f"[QueryRewrite] Rewritten: {rewritten_query}")
        return {"rewritten_query": rewritten_query}

    except Exception as e:
        logger.error(f"[QueryRewrite] Error: {e}")
        return {"rewritten_query": user_query}
