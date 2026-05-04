"""Chat 会话 & 消息服务 — 对齐 Java ChatSessionService + ChatMessageService"""
import uuid
from datetime import datetime
from typing import Optional, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete
from sqlalchemy.orm import selectinload

from ..models.chat_session import ChatSession
from ..models.chat_message import ChatMessage
from ..services.session_event_publisher import SessionEventPublisher


class ChatService:
    """会话 & 消息管理服务"""

    # ==================================================================
    # Session CRUD
    # ==================================================================

    @staticmethod
    async def list_sessions(db: AsyncSession, agent_id: int) -> List[ChatSession]:
        """获取 Agent 的所有会话 — 对齐 Java findByAgentId"""
        result = await db.execute(
            select(ChatSession)
            .where(ChatSession.agent_id == agent_id, ChatSession.status == "active")
            .order_by(ChatSession.is_pinned.desc(), ChatSession.update_time.desc())
        )
        return result.scalars().all()

    @staticmethod
    async def create_session(
        db: AsyncSession, agent_id: int, title: str = "新对话", user_id: Optional[int] = None
    ) -> ChatSession:
        """创建新会话 — 对齐 Java createSession"""
        session = ChatSession(
            id=str(uuid.uuid4()),
            agent_id=agent_id,
            title=title,
            user_id=user_id,
        )
        db.add(session)
        await db.commit()
        await db.refresh(session)
        return session

    @staticmethod
    async def clear_sessions(db: AsyncSession, agent_id: int) -> int:
        """清空 Agent 的所有会话 — 对齐 Java clearSessionsByAgentId"""
        result = await db.execute(
            delete(ChatSession).where(ChatSession.agent_id == agent_id)
        )
        await db.commit()
        return result.rowcount

    @staticmethod
    async def get_session(db: AsyncSession, session_id: str) -> Optional[ChatSession]:
        """获取单个会话"""
        result = await db.execute(
            select(ChatSession).where(ChatSession.id == session_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def update_session_time(db: AsyncSession, session_id: str):
        """更新会话活动时间 — 对齐 Java updateSessionTime"""
        session = await ChatService.get_session(db, session_id)
        if session:
            session.update_time = datetime.utcnow()
            await db.commit()

    @staticmethod
    async def pin_session(db: AsyncSession, session_id: str, is_pinned: bool):
        """置顶/取消置顶会话 — 对齐 Java pinSession"""
        session = await ChatService.get_session(db, session_id)
        if session:
            session.is_pinned = is_pinned
            await db.commit()

    @staticmethod
    async def rename_session(db: AsyncSession, session_id: str, title: str):
        """重命名会话 — 对齐 Java renameSession + SessionEventPublisher"""
        session = await ChatService.get_session(db, session_id)
        if session:
            session.title = title.strip()
            await db.commit()
            # Push title update event to SSE subscribers
            await SessionEventPublisher.publish_title_updated(
                session.agent_id, session_id, session.title
            )

    @staticmethod
    async def delete_session(db: AsyncSession, session_id: str) -> bool:
        """软删除单个会话 — 对齐 Java deleteSession"""
        session = await ChatService.get_session(db, session_id)
        if not session:
            return False
        session.status = "deleted"
        await db.commit()
        return True

    # ==================================================================
    # Message CRUD
    # ==================================================================

    @staticmethod
    async def list_messages(db: AsyncSession, session_id: str) -> List[ChatMessage]:
        """获取会话的所有消息 — 对齐 Java findBySessionId"""
        result = await db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.create_time.asc())
        )
        return result.scalars().all()

    @staticmethod
    async def save_message(
        db: AsyncSession,
        session_id: str,
        role: str,
        content: str,
        message_type: str = "text",
        metadata: Optional[dict] = None,
    ) -> ChatMessage:
        """保存消息 — 对齐 Java saveMessage"""
        message = ChatMessage(
            session_id=session_id,
            role=role,
            content=content,
            message_type=message_type,
            metadata_=metadata,
        )
        db.add(message)
        await db.commit()
        await db.refresh(message)

        # Update session activity time
        await ChatService.update_session_time(db, session_id)
        return message

    @staticmethod
    async def delete_messages(db: AsyncSession, session_id: str) -> int:
        """删除会话的所有消息"""
        result = await db.execute(
            delete(ChatMessage).where(ChatMessage.session_id == session_id)
        )
        await db.commit()
        return result.rowcount
