"""
查询改写节点（Query Rewrite Node）
基于知识库改写用户查询
"""
from typing import Dict, Any
from ..state import AgentState
from ..core.llm import get_llm_client
from ..core.config import settings
import logging

logger = logging.getLogger(__name__)


async def query_rewrite_node(state: AgentState) -> Dict[str, Any]:
    """
    查询改写节点

    基于召回的知识改写用户查询，将业务术语映射为技术术语

    Args:
        state: 工作流状态

    Returns:
        更新后的状态
    """
    user_query = state["user_query"]
    recalled_knowledge = state.get("recalled_knowledge", "")

    logger.info(f"[QueryRewrite] Rewriting query: {user_query}")

    # 如果没有召回到知识，直接返回原查询
    if not recalled_knowledge:
        logger.info("[QueryRewrite] No knowledge recalled, using original query")
        return {"rewritten_query": user_query}

    try:
        llm = get_llm_client()

        # 构建改写 Prompt
        prompt = f"""你是一个查询改写助手。根据提供的业务知识，将用户的业务查询改写为更精确的技术查询。

{recalled_knowledge}

用户查询: {user_query}

请根据上述知识，改写用户查询。改写规则：
1. 将业务术语替换为对应的技术术语或字段名
2. 补充必要的业务规则和约束条件
3. 保持查询的原始意图不变
4. 如果知识中没有相关信息，保持原查询不变

只返回改写后的查询，不要解释。"""

        response = await llm.chat.completions.create(
            model=settings.openai_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0
        )

        rewritten_query = response.choices[0].message.content.strip()

        logger.info(f"[QueryRewrite] Rewritten query: {rewritten_query}")

        return {"rewritten_query": rewritten_query}

    except Exception as e:
        logger.error(f"[QueryRewrite] Error: {e}")
        # 出错时返回原查询
        return {"rewritten_query": user_query}
