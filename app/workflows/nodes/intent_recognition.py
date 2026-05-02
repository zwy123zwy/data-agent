"""
工作流节点：意图识别
"""
from ..state import WorkflowState
from ..core.llm import llm_service


INTENT_SYSTEM_PROMPT = """你是一个意图识别助手。
你的任务是判断用户的问题是否需要查询数据库。

如果用户的问题是：
- 数据查询、统计、分析相关 → 返回 "data_analysis"
- 闲聊、问候、无关问题 → 返回 "chitchat"

只返回 "data_analysis" 或 "chitchat"，不要有其他内容。
"""


async def intent_recognition_node(state: WorkflowState) -> WorkflowState:
    """
    意图识别节点

    判断用户问题是否需要查询数据库
    """
    user_query = state["user_query"]

    # 调用 LLM 进行意图识别
    user_prompt = f"用户问题：{user_query}"

    try:
        intent = await llm_service.chat(INTENT_SYSTEM_PROMPT, user_prompt)
        intent = intent.strip().lower()

        # 验证返回值
        if intent not in ["data_analysis", "chitchat"]:
            intent = "chitchat"  # 默认为闲聊

        state["intent"] = intent

    except Exception as e:
        state["error"] = f"Intent recognition failed: {str(e)}"
        state["intent"] = "chitchat"

    return state
