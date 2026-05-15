
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from ..core.database import Base

# 模型配置表 -基础类

class ModelConfig(Base):
    __tablename__ = "model_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String(255), nullable=False, comment="厂商标识")
    base_url: Mapped[str] = mapped_column(String(255), nullable=False, default="", comment="API Base URL")
    api_key: Mapped[str] = mapped_column(String(255), nullable=False, default="", comment="API密钥")
    model_name: Mapped[str] = mapped_column(String(255), nullable=False, default="", comment="模型名称")
    model_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="CHAT", comment="模型类型: CHAT/EMBEDDING"
    )
    temperature: Mapped[float] = mapped_column(default=0.0, comment="温度参数")
    is_active: Mapped[int] = mapped_column(Integer, default=0, comment="是否激活：0-否，1-是")
    max_tokens: Mapped[Optional[int]] = mapped_column(Integer, default=2000, comment="最大 Token 数")
    completions_path: Mapped[Optional[str]] = mapped_column(String(255), comment="Chat completions 路径")
    embeddings_path: Mapped[Optional[str]] = mapped_column(String(255), comment="Embedding 路径")
    proxy_enabled: Mapped[int] = mapped_column(Integer, default=0, comment="代理开关：0-禁用，1-启用")
    proxy_host: Mapped[Optional[str]] = mapped_column(String(255), comment="代理主机")
    proxy_port: Mapped[Optional[int]] = mapped_column(Integer, comment="代理端口")
    proxy_username: Mapped[Optional[str]] = mapped_column(String(255), comment="代理用户名")
    proxy_password: Mapped[Optional[str]] = mapped_column(String(255), comment="代理密码")
    is_deleted: Mapped[int] = mapped_column(Integer, default=0, comment="0=未删除, 1=已删除")
    created_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_time: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间"
    )

    def __repr__(self):
        return f"<ModelConfig(id={self.id}, provider='{self.provider}', model='{self.model_name}')>"
