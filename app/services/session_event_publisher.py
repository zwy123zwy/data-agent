"""SessionEventPublisher — 对齐 Java SessionEventPublisher，per-agent SSE 广播"""
import asyncio
import logging
from typing import Dict, Set
from ..schemas.session_event import SessionUpdateEvent

logger = logging.getLogger(__name__)


class SessionEventPublisher:
    """管理 SSE 流，将会话更新推送给前端。一个 agent 对应一组共享的 asyncio.Queue"""

    _queues: Dict[int, Set[asyncio.Queue]] = {}
    _lock = asyncio.Lock()

    @classmethod
    async def register(cls, agent_id: int) -> asyncio.Queue:
        """注册一个新的 SSE 订阅者 — 对齐 Java register()"""
        async with cls._lock:
            if agent_id not in cls._queues:
                cls._queues[agent_id] = set()
            queue: asyncio.Queue = asyncio.Queue(maxsize=256)
            cls._queues[agent_id].add(queue)
            logger.debug(
                "Registered subscriber for agent %d, current count: %d",
                agent_id, len(cls._queues[agent_id]),
            )
            return queue

    @classmethod
    async def unregister(cls, agent_id: int, queue: asyncio.Queue):
        """注销一个 SSE 订阅者 — 对齐 Java cleanup()"""
        async with cls._lock:
            if agent_id in cls._queues:
                cls._queues[agent_id].discard(queue)
                remaining = len(cls._queues[agent_id])
                if remaining == 0:
                    del cls._queues[agent_id]
                    logger.debug("Removed session update sink for agent %d", agent_id)
                else:
                    logger.debug(
                        "Cleanup for agent %d, remaining subscribers: %d", agent_id, remaining
                    )

    @classmethod
    async def publish_title_updated(cls, agent_id: int, session_id: str, title: str):
        """推送标题更新事件 — 对齐 Java publishTitleUpdated()"""
        if agent_id is None:
            return
        event = SessionUpdateEvent.title_updated(session_id, title)
        async with cls._lock:
            queues = list(cls._queues.get(agent_id, set()))
        if not queues:
            logger.debug("No active subscribers for agent %d, skip pushing", agent_id)
            return
        for q in queues:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning(
                    "Queue full for agent %d, dropping title update event", agent_id
                )
