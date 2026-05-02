"""
多轮对话上下文管理（Multi-Turn Context Manager） — 对齐 Java MultiTurnContextManager
管理对话历史，注入后续 prompt，限制轮次
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
