"""BusinessKnowledge ORM — 对齐 Java business_knowledge 表"""
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Text, DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column
from ..core.database import Base


class BusinessKnowledge(Base):
    __tablename__ = "business_knowledge"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    business_term: Mapped[str] = mapped_column(String(255), nullable=False, comment="业务名词")
    description: Mapped[Optional[str]] = mapped_column(Text, comment="描述")
    synonyms: Mapped[Optional[str]] = mapped_column(Text, comment="同义词，逗号分隔")
    is_recall: Mapped[int] = mapped_column(Integer, default=1, comment="是否召回: 0=不召回, 1=召回")
    agent_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True, comment="关联的智能体ID")
    embedding_status: Mapped[Optional[str]] = mapped_column(String(20), default=None, comment="向量化状态: PENDING/PROCESSING/COMPLETED/FAILED")
    error_msg: Mapped[Optional[str]] = mapped_column(String(255), comment="错误信息")
    is_deleted: Mapped[int] = mapped_column(Integer, default=0, comment="0=未删除, 1=已删除")
    created_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_time: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间"
    )

    def __repr__(self):
        return f"<BusinessKnowledge(id={self.id}, term={self.business_term})>"
