# [阶段4] 会话 thread 工作记忆：DB 消息 → MultiTurn 同步（Harness Memory #4）

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.services.chat_service import ChatService
from app.services.multi_turn import get_multi_turn_manager

logger = logging.getLogger(__name__)


async def ensure_multi_turn_hydrated(db: AsyncSession, thread_id: str) -> int:
    """Run 前刷新工作记忆。

    - db：每 Run 从 chat_message 同步（merge/replace 见配置），多实例一致。
    - memory：仅进程内无历史时回填（开发/单测兼容）。

    约定：threadId = chat_session.id = chat_message.session_id。

    Returns:
        同步后的总轮次数（0 表示无消息或未变更）
    """
    if not thread_id:
        return 0

    mgr = get_multi_turn_manager()
    backend = (settings.multi_turn_backend or "db").lower()

    if backend == "memory" and mgr.get_turn_count(thread_id) > 0:
        return 0

    messages = await ChatService.list_messages(db, thread_id)
    if not messages:
        return 0

    if backend == "db":
        return mgr.sync_from_db_messages(thread_id, messages)

    added = mgr.hydrate_from_chat_messages(thread_id, messages)
    if added:
        logger.info(
            "[MultiTurn] Hydrated thread_id=%s from DB: %d turns (memory backend)",
            thread_id,
            added,
        )
    return added


def resolve_stream_thread_id(thread_id: str | None, session_id: str | None = None) -> str:
    """[阶段4] 统一流式 thread_id：优先显式 threadId，否则 sessionId（= 会话主键）。"""
    tid = (thread_id or session_id or "").strip()
    if tid:
        return tid
    import uuid

    return str(uuid.uuid4())
