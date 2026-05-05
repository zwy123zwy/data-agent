"""ChatMessage 消息模型 - 对齐 Java ChatMessage"""
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column
from ..core.database import Base


class ChatMessage(Base):
    __tablename__ = "chat_message"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("chat_session.id", ondelete="CASCADE"),
        nullable=False, comment="会话ID"
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False, comment="角色: user/assistant/system")
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="消息内容")
    message_type: Mapped[str] = mapped_column(
        String(50), default="text",
        comment="消息类型: text/sql/result/error/html/result-set/html-report/markdown-report/json/python"
    )
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSON, comment="元数据（JSON格式）")
    create_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, comment="创建时间")
