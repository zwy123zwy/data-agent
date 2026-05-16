"""
意图识别节点 — 对齐 Java IntentRecognitionNode

Harness 角色: 入口节点，识别用户是想做数据分析还是闲聊。
若非数据分析则短路返回，避免后续节点无效执行。

I/O 契约:
  requires: user_query, multi_turn_context
  provides: intent, classification
"""

from ..state import WorkflowState
from ..node_base import WorkflowNode, SSEPayload
from ...core.llm import llm_service
from ...core.text_utils import clean_code_block
import json
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

INTENT_SYSTEM_PROMPT = """你是一个意图识别助手。
你的任务是判断用户的问题是否需要查询数据库并进行数据分析。

如果用户的问题是：
- 数据查询、统计、分析、报表相关 → 返回 "data_analysis"
- 闲聊、问候、感谢、无关问题 → 返回 "chitchat"

返回 JSON 格式:
{
  "intent": "data_analysis" | "chitchat",
  "classification": "意图分类说明"
}
"""


class IntentRecognitionNode(WorkflowNode):
    """意图识别 — 对齐 Java IntentRecognitionNode.apply()

    判断用户是想做数据分析还是闲聊。
    若为闲聊则设置 intent=chitchat，路由层据此短路到 END。
    """

    name = "intent_recognition"
    description = "识别用户意图，判断是数据分析还是闲聊"
    requires = ["user_query", "multi_turn_context"]
    provides = ["intent", "classification"]
    applicable_data_sources = ["*"]

    async def execute(self, state: WorkflowState) -> Dict[str, Any]:
        user_query = state["user_query"]
        multi_turn = state.get("multi_turn_context", "")

        if multi_turn:
            user_prompt = (
                f"多轮对话上下文:\n{multi_turn}\n\n"
                f"当前用户问题: {user_query}"
            )
        else:
            user_prompt = f"用户问题: {user_query}"

        logger.info(f"[IntentRecognition] Input: {user_query}")

        try:
            llm_output = await llm_service.chat(INTENT_SYSTEM_PROMPT, user_prompt)
            llm_output = llm_output.strip()

            try:
                text = clean_code_block(llm_output, lang="json")
                data = json.loads(text)
                intent = data.get("intent", "").strip().lower()
                classification = data.get("classification", "")
            except (json.JSONDecodeError, Exception):
                intent = llm_output.lower()
                classification = ""

            if intent not in ("data_analysis", "chitchat"):
                intent = "chitchat"

            if not classification:
                classification = "可能的数据分析请求" if intent == "data_analysis" else "闲聊或无关指令"

            logger.info(f"[IntentRecognition] Result: intent={intent}")
            return {"intent": intent, "classification": classification}

        except Exception as e:
            logger.error(f"[IntentRecognition] Error: {e}")
            return {
                "intent": "chitchat",
                "classification": "闲聊或无关指令",
                "error": f"LLM 意图识别失败 (请检查 API Key 是否有效): {str(e)}",
            }

    def format_sse(self, output: Dict[str, Any]) -> SSEPayload:
        """意图识别进度 + 分类结果"""
        intent = output.get("intent", "")
        classification = output.get("classification", "")
        json_part = json.dumps({"classification": classification}, ensure_ascii=False)
        return SSEPayload(
            text=f"正在进行意图识别...{json_part}\n意图识别完成！",
            text_type="TEXT",
            metrics_delta={"intent_classification": intent},
        )


# LangGraph 兼容实例
intent_recognition_node = IntentRecognitionNode()
