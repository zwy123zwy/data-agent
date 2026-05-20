# [阶段4] agent_run 表 — V2 Run 持久化

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AgentRun(Base):
    """[阶段4] 一次 V2 runtime 执行的元数据。"""

    __tablename__ = "agent_run"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, comment="run_id UUID")
    agent_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("agent.id", ondelete="CASCADE"), nullable=False
    )
    thread_id: Mapped[str] = mapped_column(String(36), nullable=False)
    mode: Mapped[str] = mapped_column(String(32), default="smart_query")
    status: Mapped[str] = mapped_column(String(32), default="running")
    user_query: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    create_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    update_time: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
