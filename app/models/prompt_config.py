"""
UserPromptConfig ORM Model — 对齐 Java UserPromptConfig
用户自定义 Prompt 配置，支持按 Agent + PromptType 多维度配置
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Text, DateTime, Integer, Index
from sqlalchemy.orm import Mapped, mapped_column
from ..core.database import Base


class PromptConfig(Base):
    __tablename__ = "user_prompt_config"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=None, comment="UUID 主键")
    name: Mapped[str] = mapped_column(String(255), nullable=False, comment="配置名称")
    prompt_type: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True,
        comment="提示词类型: planner/report-generator/...；Harness V2: harness-gateway、harness-chitchat、harness-clarify 等，见 docs/PROMPT-ARCHITECTURE.md"
    )
    agent_id: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, index=True,
        comment="Agent ID, null=全局配置"
    )
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False, comment="自定义系统提示词内容")
    enabled: Mapped[int] = mapped_column(Integer, default=1, comment="是否启用: 0/1")
    description: Mapped[Optional[str]] = mapped_column(Text, comment="配置描述")
    priority: Mapped[int] = mapped_column(Integer, default=0, comment="优先级 (越大越优先)")
    display_order: Mapped[int] = mapped_column(Integer, default=0, comment="显示顺序")
    creator: Mapped[Optional[str]] = mapped_column(String(255), comment="创建者")
    create_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, comment="创建时间")
    update_time: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间"
    )

    # 索引 — 对齐 Java
    __table_args__ = (
        Index("idx_enabled", "enabled"),
        Index("idx_create_time", "create_time"),
        Index("idx_prompt_type_enabled_priority", "prompt_type", "agent_id", "enabled", "priority"),
        Index("idx_display_order", "display_order"),
    )

    def __repr__(self):
        return f"<PromptConfig(id={self.id}, type={self.prompt_type}, name={self.name})>"
