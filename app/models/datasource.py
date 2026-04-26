from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from ..core.database import Base


class Datasource(Base):
    """Datasource 模型 - 对齐 Java 版本"""
    __tablename__ = "datasource"

    # 基础字段
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="数据源名称")
    type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="数据库类型: mysql/postgresql/sqlite"
    )

    # 连接信息
    host: Mapped[Optional[str]] = mapped_column(String(255), comment="主机地址")
    port: Mapped[Optional[int]] = mapped_column(Integer, comment="端口号")
    database: Mapped[str] = mapped_column(String(100), nullable=False, comment="数据库名")
    username: Mapped[Optional[str]] = mapped_column(String(100), comment="用户名")
    password: Mapped[Optional[str]] = mapped_column(String(255), comment="密码")
    connection_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        comment="完整连接字符串（SQLite使用）"
    )

    # 状态
    test_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="untested",
        comment="测试状态: untested/success/failed"
    )

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

    def __repr__(self):
        return f"<Datasource(id={self.id}, name='{self.name}', type='{self.type}')>"
