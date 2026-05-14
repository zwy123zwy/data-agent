from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, DateTime, Text, Index
from sqlalchemy.orm import Mapped, mapped_column
from ..core.database import Base


class Datasource(Base):
    """Datasource 模型 - 对齐 Java datasource 表"""
    __tablename__ = "datasource"

    # 基础字段
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, comment="数据源名称")
    type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="数据库类型: mysql/postgresql/sqlite"
    )

    # 连接信息 — 对齐 Java: 全部 NOT NULL
    host: Mapped[str] = mapped_column(String(255), nullable=False, comment="主机地址")
    port: Mapped[int] = mapped_column(Integer, nullable=False, comment="端口号")
    database_name: Mapped[str] = mapped_column(String(255), nullable=False, comment="数据库名")
    username: Mapped[str] = mapped_column(String(255), nullable=False, comment="用户名")
    password: Mapped[str] = mapped_column(String(255), nullable=False, comment="密码（加密存储）")
    connection_url: Mapped[Optional[str]] = mapped_column(
        String(1000),
        comment="完整 JDBC URL"
    )

    # 状态 — 对齐 Java 默认值
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="inactive",
        comment="状态: active/inactive"
    )
    test_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="unknown",
        comment="连接测试结果: success/failed/unknown"
    )

    # 扩展字段
    description: Mapped[Optional[str]] = mapped_column(Text, comment="数据源描述")
    creator_id: Mapped[Optional[int]] = mapped_column(Integer, comment="创建者用户 ID")

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

    # 索引 — 对齐 Java
    __table_args__ = (
        Index("idx_name", "name"),
        Index("idx_type", "type"),
        Index("idx_status", "status"),
        Index("idx_creator_id", "creator_id"),
    )

    def __repr__(self):
        return f"<Datasource(id={self.id}, name='{self.name}', type='{self.type}')>"
