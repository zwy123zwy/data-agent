"""
查询改写节点 — 对齐 Java QueryEnhanceNode

Harness 角色: 将用户的业务术语改写为技术术语，
基于知识库召回结果补充上下文，使后续 Schema/SQL 节点更精确。

I/O 契约:
  requires: user_query, recalled_knowledge
  provides: rewritten_query
"""

from typing import Dict, Any
from ..state import WorkflowState
from ..node_base import WorkflowNode, SSEPayload
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


class QueryRewriteNode(WorkflowNode):
    """查询改写 — 对齐 Java QueryEnhanceNode.apply()

    基于知识库召回的业务术语，将用户口语化查询改写为精确的技术查询。
    若知识库为空则原样返回。
    """

    name = "query_rewrite"
    description = "基于知识库将业务查询改写为精确的技术查询"
    requires = ["user_query", "recalled_knowledge"]
    provides = ["rewritten_query"]
    applicable_data_sources = ["*"]

    async def execute(self, state: WorkflowState) -> Dict[str, Any]:
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

    def format_sse(self, output: Dict[str, Any]) -> SSEPayload:
        rewritten = output.get("rewritten_query", "")
        # [旧代码] 不声明 Agent/Tool
        # if rewritten:
        #     return SSEPayload(text=f"正在优化查询...\n{rewritten}", text_type="TEXT")
        # return SSEPayload(text="正在优化查询...(使用原始查询)", text_type="TEXT")
        # V3.0: 声明 Explorer 归属 + rewrite_query tool
        if rewritten:
            return SSEPayload(
                text=f"正在优化查询...\n{rewritten}", text_type="TEXT",
                agent_name="Explorer", tool_name="rewrite_query",
                tool_status="done",
            )
        return SSEPayload(
            text="正在优化查询...(使用原始查询)", text_type="TEXT",
            agent_name="Explorer", tool_name="rewrite_query",
            tool_status="done",
        )


# LangGraph 兼容实例
query_rewrite_node = QueryRewriteNode()
