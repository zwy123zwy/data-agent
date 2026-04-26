from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Text, DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ..core.database import Base


class Agent(Base):
    """Agent 模型 - 对齐 Java 版本"""
    __tablename__ = "agent"

    # 基础字段
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="Agent名称")
    description: Mapped[Optional[str]] = mapped_column(Text, comment="Agent描述")
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="draft",
        comment="状态: draft/published/offline"
    )

    # 扩展字段（对齐Java版本，Phase 1暂不使用）
    avatar: Mapped[Optional[str]] = mapped_column(String(255), comment="头像URL")
    tags: Mapped[Optional[str]] = mapped_column(String(500), comment="标签，逗号分隔")
    api_key: Mapped[Optional[str]] = mapped_column(String(64), comment="API Key")
    api_key_enabled: Mapped[bool] = mapped_column(default=False, comment="API Key是否启用")

    # 时间戳
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        comment="创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        comment="更新时间"
    )

    # 关系（Phase 1 暂不使用，为后续扩展预留）
    # datasources: Mapped[List["AgentDatasource"]] = relationship(
    #     back_populates="agent",
    #     cascade="all, delete-orphan"
    # )

    def __repr__(self):
        return f"<Agent(id={self.id}, name='{self.name}', status='{self.status}')>"
