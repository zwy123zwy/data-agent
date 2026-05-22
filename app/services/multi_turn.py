"""
[阶段4] 多轮对话上下文管理 — Harness Memory #4 门面

工作记忆读路径在 multi_turn_backend=db 时以 chat_message 为 SSOT，
经 multi_turn_store 配对后同步到进程内 contexts；add_turn 仍写内存尾部供 merge。
设计文档：docs/ARCHITECTURE.md（L4 §6）
"""
from typing import List, Dict, Any, Optional, Sequence
from ..core.config import settings
import logging

from .multi_turn_store import merge_db_and_memory_turns, pair_messages_to_turns

logger = logging.getLogger(__name__)

MAX_TURNS = 5  # 默认最大对话轮次
_HYDRATE_USER_MAX = 500
_HYDRATE_ASSISTANT_MAX = 500


class MultiTurnContext:
    """[阶段4] 单轮对话上下文（user / assistant 摘要）"""

    def __init__(self, user_query: str, response: str, turn_number: int):
        self.user_query = user_query
        self.response = response
        self.turn_number = turn_number


class MultiTurnContextManager:
    """[阶段4] 多轮对话上下文管理器 — 门面 + 进程内 L1"""

    def __init__(self):
        self.max_turns = settings.max_turn_history
        self.contexts: Dict[str, List[MultiTurnContext]] = {}

    def _memory_pairs(self, thread_id: str) -> List[tuple[str, str]]:
        return [
            (t.user_query, t.response)
            for t in self.contexts.get(thread_id, [])
        ]

    def _apply_pairs(self, thread_id: str, pairs: List[tuple[str, str]]) -> int:
        self.contexts[thread_id] = [
            MultiTurnContext(u, r, i + 1) for i, (u, r) in enumerate(pairs)
        ]
        return len(self.contexts[thread_id])

    def sync_from_db_messages(
        self,
        thread_id: str,
        messages: Sequence[Any],
        *,
        sync_mode: str | None = None,
    ) -> int:
        """[阶段4] 从 DB 消息同步工作记忆；merge 时保留尚未落库的内存尾部。"""
        if not thread_id:
            return 0

        db_pairs = pair_messages_to_turns(messages)
        mem_pairs = self._memory_pairs(thread_id)
        mode = sync_mode or settings.multi_turn_db_sync_mode

        merged = merge_db_and_memory_turns(
            db_pairs,
            mem_pairs,
            sync_mode=mode,
            max_turns=self.max_turns,
        )

        if not merged and not mem_pairs:
            if thread_id in self.contexts:
                del self.contexts[thread_id]
            return 0

        count = self._apply_pairs(thread_id, merged)
        if db_pairs:
            logger.info(
                "[MultiTurn] Synced from DB thread_id=%s db_turns=%d total_turns=%d mode=%s",
                thread_id,
                len(db_pairs),
                count,
                mode,
            )
        return count

    def hydrate_from_chat_messages(
        self,
        thread_id: str,
        messages: Sequence[Any],
        *,
        max_turns: int | None = None,
    ) -> int:
        """[阶段4] 从持久化消息恢复轮次（memory 后端：仅当该 thread 尚无记录时写入）。"""
        if settings.multi_turn_backend == "db":
            return self.sync_from_db_messages(thread_id, messages)

        if self.get_turn_count(thread_id) > 0:
            return 0

        limit = max_turns if max_turns is not None else self.max_turns
        paired = pair_messages_to_turns(messages)[-limit:] if limit else []

        if not paired:
            return 0

        return self._apply_pairs(thread_id, paired)

    def add_turn(self, thread_id: str, user_query: str, response: str):
        """[阶段4] Feedback：追加一轮并裁剪最旧轮次"""
        if thread_id not in self.contexts:
            self.contexts[thread_id] = []

        turns = self.contexts[thread_id]
        turn_number = len(turns) + 1
        turns.append(MultiTurnContext(user_query, response, turn_number))

        if len(turns) > self.max_turns:
            self.contexts[thread_id] = turns[-self.max_turns :]
            for i, t in enumerate(self.contexts[thread_id]):
                t.turn_number = i + 1

        logger.info(
            "[MultiTurn] add_turn thread_id=%s turns=%d backend=%s",
            thread_id,
            len(self.contexts[thread_id]),
            settings.multi_turn_backend,
        )

    def get_context_text(self, thread_id: str) -> str:
        """[阶段4] 获取格式化的 Markdown 历史上下文"""
        if thread_id not in self.contexts:
            return ""

        turns = self.contexts[thread_id]
        if not turns:
            return ""

        parts = ["## 历史对话上下文"]
        for t in turns:
            parts.append(f"**用户 (轮次{t.turn_number})**: {t.user_query}")
            resp = (t.response or "").strip()
            preview = resp[:300] + ("..." if len(resp) > 300 else "")
            parts.append(f"**助手**: {preview}")
        parts.append("---\n请基于以上历史上下文回答当前问题。")

        return "\n\n".join(parts)

    def get_context_for_prompt(self, thread_id: str) -> str:
        """[阶段4] 获取注入 prompt 的上下文 — 对齐 Java"""
        return self.get_context_text(thread_id)

    def get_messages_for_llm(
        self,
        thread_id: str,
        max_turns: int = 3,
    ) -> List[Dict[str, str]]:
        """[阶段4] 转为 Gateway / LLM 结构化消息列表"""
        turns = self.contexts.get(thread_id, [])
        if not turns:
            return []

        limit = max(1, min(max_turns, self.max_turns))
        messages: List[Dict[str, str]] = []
        for t in turns[-limit:]:
            uq = (t.user_query or "").strip()
            if uq:
                messages.append({"role": "user", "content": uq[:500]})
            resp = (t.response or "").strip()
            if resp:
                messages.append({"role": "assistant", "content": resp[:500]})
        return messages

    def clear(self, thread_id: str):
        """[阶段4] 清除会话工作记忆"""
        if thread_id in self.contexts:
            del self.contexts[thread_id]
            logger.info(f"[MultiTurn] Cleared thread: {thread_id}")

    def get_turn_count(self, thread_id: str) -> int:
        return len(self.contexts.get(thread_id, []))

    def is_exceeded(self, thread_id: str) -> bool:
        return self.get_turn_count(thread_id) >= self.max_turns


_multi_turn_manager: Optional[MultiTurnContextManager] = None


def get_multi_turn_manager() -> MultiTurnContextManager:
    """[阶段4] 多轮对话上下文管理器全局单例"""
    global _multi_turn_manager
    if _multi_turn_manager is None:
        _multi_turn_manager = MultiTurnContextManager()
    return _multi_turn_manager
