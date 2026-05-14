"""
工作流节点：意图识别 — 对齐 Java IntentRecognitionNode

【模块连接】
  上游: graph.py entry_point → LangGraph 从 START 路由到此节点
  下游: state["intent"], state["classification"]
  路由: "data_analysis" → knowledge_recall, "chitchat" → END

  Java 对应: IntentRecognitionNode.java
"""
from ..state import WorkflowState
from ...core.llm import llm_service
from ...core.text_utils import clean_code_block
import json
import logging

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


async def intent_recognition_node(state: WorkflowState) -> WorkflowState:
    """意图识别节点 — 对齐 Java IntentRecognitionNode.apply()

    读取: state["user_query"], state["multi_turn_context"]
    写入: state["intent"], state["classification"]
    """
    user_query = state["user_query"]
    multi_turn = state.get("multi_turn_context", "")

    # 对齐 Java: 传入多轮上下文
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

        # 尝试 JSON 解析 — 对齐 Java IntentRecognitionOutputDTO
        try:
            text = clean_code_block(llm_output, lang="json")
            data = json.loads(text)
            intent = data.get("intent", "").strip().lower()
            classification = data.get("classification", "")
        except (json.JSONDecodeError, Exception):
            # 纯文本降级
            intent = llm_output.lower()
            classification = ""

        # 验证意图
        if intent not in ("data_analysis", "chitchat"):
            intent = "chitchat"

        if not classification:
            classification = "可能的数据分析请求" if intent == "data_analysis" else "闲聊或无关指令"

        state["intent"] = intent
        state["classification"] = classification
        logger.info(f"[IntentRecognition] Result: intent={intent}")

    except Exception as e:
        state["error"] = f"LLM 意图识别失败 (请检查 API Key 是否有效): {str(e)}"
        state["intent"] = "chitchat"
        state["classification"] = "闲聊或无关指令"
        logger.error(f"[IntentRecognition] Error: {e}")

    return state
