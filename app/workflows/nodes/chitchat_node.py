"""
闲聊响应节点 — 意图识别为非数据分析时的对话回复

Harness 角色: 当 intent != data_analysis 时，提供 LLM 驱动的对话式回复，
而非仅结束流程。

I/O 契约:
  requires: user_query, multi_turn_context
  provides: chitchat_response
"""
from typing import Dict, Any
import logging

from ..state import WorkflowState
from ..node_base import WorkflowNode, SSEPayload
from ...core.llm import llm_service

logger = logging.getLogger(__name__)

CHITCHAT_SYSTEM_PROMPT = """你是一个友好的 AI 数据分析助手。
用户当前的问题不涉及数据库查询或数据分析，请用自然、简洁的语言回复。
如果用户打招呼，热情回应；如果用户问你的能力，介绍你能做数据查询和分析。
始终用中文回复。"""


class ChitchatNode(WorkflowNode):
    """闲聊回复 — 用 LLM 生成自然的对话回复"""

    name = "chitchat_node"
    description = "闲聊回复 — 当意图非数据分析时，用 LLM 生成对话式回复"
    requires = ["user_query", "multi_turn_context"]
    provides = ["chitchat_response"]
    applicable_data_sources = ["*"]

    async def execute(self, state: WorkflowState) -> Dict[str, Any]:
        user_query = state.get("user_query", "")
        multi_turn = state.get("multi_turn_context", "")

        # 拼接上下文
        if multi_turn:
            prompt = f"对话历史:\n{multi_turn}\n\n当前问题: {user_query}"
        else:
            prompt = user_query

        logger.info(f"[Chitchat] query={user_query[:80]}")

        try:
            response = await llm_service.chat(CHITCHAT_SYSTEM_PROMPT, prompt)
            response = response.strip()
            logger.info(f"[Chitchat] response={response[:100]}")
        except Exception as e:
            logger.error(f"[Chitchat] LLM failed: {e}")
            response = "抱歉，我暂时无法回复，请稍后再试。"

        return {"chitchat_response": response}

    def format_sse(self, output: Dict[str, Any]) -> SSEPayload | None:
        text = output.get("chitchat_response", "")
        if text:
            # [旧代码] 不声明 Agent/Tool
            # return SSEPayload(text=text, text_type="TEXT")
            # V3.0: 声明 Explorer 归属 (闲聊回复为终端节点)
            return SSEPayload(
                text=text, text_type="TEXT",
                agent_name="Explorer",
            )
        return None


# LangGraph 兼容实例
chitchat_node = ChitchatNode()
