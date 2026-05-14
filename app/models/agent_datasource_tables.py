"""AgentDatasourceTables 数据源表选择模型 - 对齐 Java agent_datasource_tables"""
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from ..core.database import Base


class AgentDatasourceTables(Base):
    __tablename__ = "agent_datasource_tables"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent_datasource_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("agent_datasource.id", onupdate="cascade", ondelete="cascade"),
        nullable=False, comment="智能体数据源ID"
    )
    table_name: Mapped[str] = mapped_column(String(255), nullable=False, comment="数据表名")
    create_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, comment="创建时间")
    update_time: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间"
    )

    # 约束 — 对齐 Java: 同一关联下不允许重复表
    __table_args__ = (
        UniqueConstraint("agent_datasource_id", "table_name", name="uk_agent_ds_table"),
    )
