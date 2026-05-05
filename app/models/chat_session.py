"""ChatSession 会话模型 - 对齐 Java ChatSession"""
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from ..core.database import Base


class ChatSession(Base):
    __tablename__ = "chat_session"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, comment="会话ID（UUID）")
    agent_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("agent.id", ondelete="CASCADE"),
        nullable=False, comment="智能体ID"
    )
    title: Mapped[str] = mapped_column(String(255), default="新对话", comment="会话标题")
    status: Mapped[str] = mapped_column(
        String(50), default="active",
        comment="状态: active/archived/deleted"
    )
    is_pinned: Mapped[int] = mapped_column(Integer, default=0, comment="是否置顶: 0/1")
    user_id: Mapped[Optional[int]] = mapped_column(Integer, comment="用户ID")
    create_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, comment="创建时间")
    update_time: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间"
    )
