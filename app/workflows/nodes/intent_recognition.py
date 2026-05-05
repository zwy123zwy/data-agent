"""
工作流节点：意图识别 — 对齐 Java IntentRecognitionNode

【在系统中的地位】
  这是整个 LangGraph 工作流的第一个节点 (入口节点)。
  所有用户请求都先经过这里，判断是数据分析还是闲聊。

【模块连接】
  上游:
    - graph.py (entry_point) → LangGraph 自动从 START 路由到此节点
    - state["user_query"]    → 由 streaming_graph_controller 在初始 state 中设置

  下游 (写入 state):
    - state["intent"] → "data_analysis" 或 "chitchat"

  路由决策 (graph.py route_after_intent):
    - "data_analysis" → knowledge_recall (继续工作流)
    - "chitchat"      → END (结束)

  LLM 依赖:
    - core/llm.py:llm_service.chat() → 调用大模型判断意图

  Java 对应:
    intent_recognition_node ≈ IntentRecognitionNode.java
"""
from ..state import WorkflowState
from ...core.llm import llm_service


INTENT_SYSTEM_PROMPT = """你是一个意图识别助手。
你的任务是判断用户的问题是否需要查询数据库。

如果用户的问题是：
- 数据查询、统计、分析相关 → 返回 "data_analysis"
- 闲聊、问候、无关问题 → 返回 "chitchat"

只返回 "data_analysis" 或 "chitchat"，不要有其他内容。
"""


async def intent_recognition_node(state: WorkflowState) -> WorkflowState:
    """
    意图识别节点 — 工作流入口

    读取:  state["user_query"]
    写入:  state["intent"], state["classification"]
    调用:  llm_service.chat() → LLM 意图分类
    """
    user_query = state["user_query"]

    user_prompt = f"用户问题：{user_query}"

    try:
        intent = await llm_service.chat(INTENT_SYSTEM_PROMPT, user_prompt)
        intent = intent.strip().lower()

        if intent not in ["data_analysis", "chitchat"]:
            intent = "chitchat"

        state["intent"] = intent
        # 对齐 Java IntentRecognitionOutputDTO.classification
        state["classification"] = "可能的数据分析请求" if intent == "data_analysis" else "闲聊或无关指令"

    except Exception as e:
        # LLM 调用失败时不要静默降级，让调用方看到具体错误
        state["error"] = f"LLM 意图识别失败 (请检查 API Key 是否有效): {str(e)}"
        state["intent"] = "chitchat"
        state["classification"] = "闲聊或无关指令"

    return state
