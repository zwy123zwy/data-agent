from datetime import datetime
from typing import Optional
from sqlalchemy import Integer, ForeignKey, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ..core.database import Base


class AgentDatasource(Base):
    """Agent-Datasource 关联模型"""
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
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="是否为当前激活的数据源"
    )

    # 时间戳
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        comment="创建时间"
    )

    # 关系（暂时注释，避免循环导入）
    # agent: Mapped["Agent"] = relationship(back_populates="datasources")
    # datasource: Mapped["Datasource"] = relationship(back_populates="agent_datasources")

    def __repr__(self):
        return f"<AgentDatasource(agent_id={self.agent_id}, datasource_id={self.datasource_id}, is_active={self.is_active})>"
