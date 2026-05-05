"""
SessionTitleService — LLM 自动生成会话标题
对齐 Java SessionTitleService
"""
import asyncio
import logging
from ..core.llm import llm_service

logger = logging.getLogger(__name__)

DEFAULT_TITLE = "新会话"
_running_tasks: set[str] = set()


async def schedule_title_generation(session_id: str, agent_id: int, user_message: str, chat_service, db_factory):
    """调度异步标题生成 — 对齐 Java scheduleTitleGeneration()

    Args:
        session_id: 会话 ID
        agent_id: Agent ID
        user_message: 用户的第一条消息
        chat_service: ChatService 模块引用（避免循环导入）
        db_factory: 异步数据库会话工厂
    """
    if not session_id or not user_message:
        return
    if session_id in _running_tasks:
        return

    _running_tasks.add(session_id)
    try:
        await _generate_and_persist(session_id, agent_id, user_message, chat_service, db_factory)
    finally:
        _running_tasks.discard(session_id)


async def _generate_and_persist(session_id: str, agent_id: int, user_message: str, chat_service, db_factory):
    """生成标题并持久化"""
    from .session_event_publisher import SessionEventPublisher

    try:
        # 检查会话是否需要生成标题
        from ..core.database import async_session_maker as async_session_factory

        async with async_session_factory() as db:
            session = await chat_service.get_session(db, session_id)
            if not session:
                logger.warning(f"Session {session_id} not found when generating title")
                return
            if _has_custom_title(session):
                logger.debug(f"Session {session_id} already has custom title, skip generating")
                return

        # 调用 LLM 生成标题
        title = await _request_summary(user_message)
        if not title:
            title = _fallback_title(user_message)

        title = _normalize_title(title)
        if not title:
            logger.warning(f"LLM returned empty title for session {session_id}")
            return

        # 持久化标题
        async with async_session_factory() as db:
            await chat_service.rename_session(db, session_id, title)
            # Note: rename_session already publishes the SSE event

        logger.info(f"Generated session title '{title}' for session {session_id}")
    except Exception as ex:
        logger.error(f"Failed to generate session title for session {session_id}: {ex}")


def _has_custom_title(session) -> bool:
    """检查会话是否已有自定义标题"""
    return bool(session.title) and session.title != DEFAULT_TITLE


async def _request_summary(user_message: str) -> str | None:
    """调用 LLM 生成不超过 20 字的会话标题"""
    try:
        system_prompt = (
            "你是一名对话助手，请根据用户的第一条输入生成不超过20个字的会话标题。"
            "使用中文输出，避免使用标点或引号，仅保留核心主题。"
        )
        user_prompt = f"用户输入：{user_message}"
        return await llm_service.chat(system_prompt, user_prompt)
    except Exception as ex:
        logger.warning(f"LLM title generation failed: {ex}")
        return None


def _normalize_title(raw: str) -> str | None:
    """规范化标题：去换行、去引号、截断到 20 字"""
    if not raw:
        return None
    sanitized = raw.replace("\r", " ").replace("\n", " ").replace('"', "").replace(""", "").replace(""", "").strip()
    if len(sanitized) > 20:
        sanitized = sanitized[:20]
    return sanitized if sanitized else None


def _fallback_title(user_message: str) -> str:
    """LLM 失败时的后备标题"""
    text = " ".join(user_message.split()).strip()
    if len(text) > 20:
        text = text[:20]
    return text if text else DEFAULT_TITLE
