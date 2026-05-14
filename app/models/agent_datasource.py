from datetime import datetime
from typing import Optional
from sqlalchemy import Integer, ForeignKey, DateTime, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ..core.database import Base


class AgentDatasource(Base):
    """Agent-Datasource 关联模型 — 对齐 Java agent_datasource 表"""
    __tablename__ = "agent_datasource"

    # 基础字段
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("agent.id", ondelete="CASCADE"),
        nullable=False,
        comment="Agent ID"
    )
    datasource_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("datasource.id", ondelete="CASCADE"),
        nullable=False,
        comment="Datasource ID"
    )
    is_active: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="是否激活: 0=否, 1=是"
    )

    # 时间戳
    create_time: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        comment="创建时间"
    )
    update_time: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        comment="更新时间"
    )

    # 约束和索引 — 对齐 Java
    __table_args__ = (
        UniqueConstraint("agent_id", "datasource_id", name="uk_agent_datasource"),
        Index("idx_agent_id", "agent_id"),
        Index("idx_datasource_id", "datasource_id"),
        Index("idx_is_active", "is_active"),
    )

    def __repr__(self):
        return f"<AgentDatasource(agent_id={self.agent_id}, datasource_id={self.datasource_id}, is_active={self.is_active})>"
