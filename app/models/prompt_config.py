"""
UserPromptConfig ORM Model — 对齐 Java UserPromptConfig
用户自定义 Prompt 配置，支持按 Agent + PromptType 多维度配置
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Text, DateTime, Integer, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from ..core.database import Base


class PromptConfig(Base):
    __tablename__ = "prompt_config"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=None, comment="UUID 主键")
    name: Mapped[str] = mapped_column(String(200), nullable=False, comment="配置名称")
    prompt_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True, comment="提示词类型: report-generator/planner/sql-generator/python-generator/rewrite")
    agent_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True, comment="Agent ID, null=全局配置")
    system_prompt: Mapped[Optional[str]] = mapped_column(Text, comment="自定义系统提示词内容")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否启用")
    description: Mapped[Optional[str]] = mapped_column(Text, comment="配置描述")
    priority: Mapped[int] = mapped_column(Integer, default=0, comment="优先级 (越大越优先)")
    display_order: Mapped[int] = mapped_column(Integer, default=0, comment="显示顺序")
    creator: Mapped[Optional[str]] = mapped_column(String(100), comment="创建者")
    create_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, comment="创建时间")
    update_time: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间"
    )

    def __repr__(self):
        return f"<PromptConfig(id={self.id}, type={self.prompt_type}, name={self.name})>"
