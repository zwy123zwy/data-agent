"""AgentPresetQuestion 预设问题模型 - 对齐 Java AgentPresetQuestion"""
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, Text, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from ..core.database import Base


class AgentPresetQuestion(Base):
    __tablename__ = "agent_preset_question"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("agent.id", ondelete="CASCADE"),
        nullable=False, comment="智能体ID"
    )
    question: Mapped[str] = mapped_column(Text, nullable=False, comment="预设问题内容")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, comment="排序顺序")
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否启用")
    create_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, comment="创建时间")
    update_time: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间"
    )
