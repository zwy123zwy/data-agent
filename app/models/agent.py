from datetime import datetime
from typing import Optional
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

    # 扩展字段（对齐Java版本）
    avatar: Mapped[Optional[str]] = mapped_column(String(255), comment="头像URL")
    tags: Mapped[Optional[str]] = mapped_column(String(500), comment="标签，逗号分隔")
    api_key: Mapped[Optional[str]] = mapped_column(String(64), comment="API Key")
    api_key_enabled: Mapped[int] = mapped_column(Integer, default=0, comment="API Key是否启用: 0/1")
    prompt: Mapped[Optional[str]] = mapped_column(Text, comment="Agent自定义Prompt")
    category: Mapped[Optional[str]] = mapped_column(String(100), comment="分类")
    admin_id: Mapped[Optional[int]] = mapped_column(Integer, comment="管理员ID")
    human_review_enabled: Mapped[int] = mapped_column(Integer, default=0, comment="是否启用人工审核: 0/1")

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

    def __repr__(self):
        return f"<Agent(id={self.id}, name='{self.name}', status='{self.status}')>"
