"""LogicalRelation 逻辑外键关系模型 - 对齐 Java LogicalRelation"""
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, DateTime, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from ..core.database import Base


class LogicalRelation(Base):
    __tablename__ = "logical_relation"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    datasource_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("datasource.id", ondelete="CASCADE"),
        nullable=False, comment="关联的数据源ID"
    )
    source_table_name: Mapped[str] = mapped_column(String(100), nullable=False, comment="主表名")
    source_column_name: Mapped[str] = mapped_column(String(100), nullable=False, comment="主表字段名")
    target_table_name: Mapped[str] = mapped_column(String(100), nullable=False, comment="关联表名")
    target_column_name: Mapped[str] = mapped_column(String(100), nullable=False, comment="关联表字段名")
    relation_type: Mapped[Optional[str]] = mapped_column(String(20), comment="关系类型: 1:1, 1:N, N:1")
    description: Mapped[Optional[str]] = mapped_column(Text, comment="业务描述")
    is_deleted: Mapped[int] = mapped_column(Integer, default=0, comment="逻辑删除: 0-未删除, 1-已删除")
    created_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_time: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间"
    )
