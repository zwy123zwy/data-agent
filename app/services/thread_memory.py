# [阶段4] 会话 thread 工作记忆：DB 消息 → MultiTurn 同步（Harness Memory #4）
#
# 两种后端模式（由 settings.multi_turn_backend 控制）:
#   "db" 模式: 每次 Run 从 chat_message 表读取全量消息，merge/replace 到进程内存。
#     优点: 多实例间最终一致（共享 MySQL），重启不丢数据。
#     缺点: 每次 Run 多一次 DB 查询。
#   "memory" 模式: 仅在进程内存无历史时回填（开发/单测兼容）。
#     优点: 零 DB 开销。缺点: 重启丢失，不适用于多实例部署。
#
# 约定: threadId = chat_session.id = chat_message.session_id

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.services.chat_service import ChatService
from app.services.multi_turn import get_multi_turn_manager

logger = logging.getLogger(__name__)


# TODO(H2): 此函数在 streaming_graph_controller 中被 Harness 分支前无条件调用，
#   但 Harness 路径不消费其结果，浪费一次 DB 查询。应移到 legacy 分支内部（或在 Harness 中利用）。
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

# TODO: 这个方法的作用是？我感知上认为应该写在其他地方
def resolve_stream_thread_id(thread_id: str | None, session_id: str | None = None) -> str:
    """[阶段4] 统一流式 thread_id：优先显式 threadId，否则 sessionId（= 会话主键）。"""
    tid = (thread_id or session_id or "").strip()
    if tid:
        return tid
    import uuid

    return str(uuid.uuid4())
