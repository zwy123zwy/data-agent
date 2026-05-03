"""
多轮对话上下文管理 — 对齐 Java MultiTurnContextManager

【在系统中的地位】
  本服务管理同一 threadId 下的多轮对话历史。当用户连续提问时，
  需要将历史对话上下文注入 LLM prompt，使 LLM 理解对话的连续性。

【模块连接】
  上游 (谁调用 MultiTurnContextManager):
    - api/streaming_graph_controller.py → 流式查询前注入历史上下文
    - api/graph_controller.py           → 同步查询前注入历史上下文
    - api/chat_controller.py            → 会话历史管理

  被依赖:
    - core/config.py → settings.max_turn_history (最大保留轮数)

  数据流:
    用户第1轮提问 → 完成 → add_turn(threadId, query, response)
    用户第2轮提问 → get_context_for_prompt(threadId) → 注入 prompt
    → LLM 理解"用户第2轮是在追问第1轮的结果"

  Java 对应:
    MultiTurnContextManager ≈ MultiTurnContextManager.java

【线程模型】
  每个 threadId 维护独立的历史轮次列表。
  最大保留 max_turn_history 轮 (默认5轮)，超出后自动裁剪最旧轮次。
"""
from typing import List, Dict, Any, Optional
from ..core.config import settings
import logging

logger = logging.getLogger(__name__)

MAX_TURNS = 5  # 默认最大对话轮次


class MultiTurnContext:
    """单轮对话上下文"""

    def __init__(self, user_query: str, response: str, turn_number: int):
        self.user_query = user_query
        self.response = response
        self.turn_number = turn_number


class MultiTurnContextManager:
    """多轮对话上下文管理器 — 对齐 Java MultiTurnContextManager"""

    def __init__(self):
        self.max_turns = settings.max_turn_history
        self.contexts: Dict[str, List[MultiTurnContext]] = {}  # thread_id → turns

    def add_turn(self, thread_id: str, user_query: str, response: str):
        """添加一轮对话"""
        if thread_id not in self.contexts:
            self.contexts[thread_id] = []

        turns = self.contexts[thread_id]
        turn_number = len(turns) + 1
        turns.append(MultiTurnContext(user_query, response, turn_number))

        # 限制最大轮次 — 对齐 Java
        if len(turns) > self.max_turns:
            self.contexts[thread_id] = turns[-self.max_turns:]

        logger.info(f"[MultiTurn] Thread {thread_id}: {len(turns)} turns")

    def get_context_text(self, thread_id: str) -> str:
        """获取格式化的上下文文本 — 对齐 Java MultiTurnContextManager.getContextText()"""
        if thread_id not in self.contexts:
            return ""

        turns = self.contexts[thread_id]
        if not turns:
            return ""

        parts = ["## 历史对话上下文"]
        for t in turns:
            parts.append(f"**用户 (轮次{t.turn_number})**: {t.user_query}")
            parts.append(f"**助手**: {t.response[:300]}...")
        parts.append("---\n请基于以上历史上下文回答当前问题。")

        return "\n\n".join(parts)

    def get_context_for_prompt(self, thread_id: str) -> str:
        """获取注入 prompt 的上下文 — 对齐 Java"""
        return self.get_context_text(thread_id)

    def clear(self, thread_id: str):
        """清除会话历史"""
        if thread_id in self.contexts:
            del self.contexts[thread_id]
            logger.info(f"[MultiTurn] Cleared thread: {thread_id}")

    def get_turn_count(self, thread_id: str) -> int:
        """获取当前轮次数"""
        return len(self.contexts.get(thread_id, []))

    def is_exceeded(self, thread_id: str) -> bool:
        """检查是否超过最大轮次"""
        return self.get_turn_count(thread_id) >= self.max_turns


# 全局实例
_multi_turn_manager: Optional[MultiTurnContextManager] = None


def get_multi_turn_manager() -> MultiTurnContextManager:
    global _multi_turn_manager
    if _multi_turn_manager is None:
        _multi_turn_manager = MultiTurnContextManager()
    return _multi_turn_manager
