"""
ModelConfig ORM 模型
模型配置 - 支持多模型管理
"""
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, JSON
from sqlalchemy.sql import func
from ..core.database import Base


class ModelConfig(Base):
    """模型配置"""
    __tablename__ = "model_config"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True, comment="模型名称")
    type = Column(String(50), nullable=False, comment="模型类型: chat, embedding")
    provider = Column(String(50), nullable=False, comment="提供商: openai, anthropic, qwen")
    model_id = Column(String(100), nullable=False, comment="模型ID")
    api_key = Column(String(255), comment="API Key")
    api_base = Column(String(255), comment="API Base URL")
    temperature = Column(Float, default=0.0, comment="温度参数")
    max_tokens = Column(Integer, comment="最大 Token 数")
    enabled = Column(Boolean, default=True, nullable=False, comment="是否启用")
    is_default = Column(Boolean, default=False, nullable=False, comment="是否默认")
    metadata_ = Column("metadata", JSON, comment="其他配置")
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    # 从 metadata_ JSON 暴露的扩展属性 (对齐 Java)
    @property
    def completions_path(self) -> Optional[str]:
        return (self.metadata_ or {}).get("completions_path")

    @property
    def embeddings_path(self) -> Optional[str]:
        return (self.metadata_ or {}).get("embeddings_path")

    @property
    def proxy_enabled(self) -> Optional[bool]:
        return (self.metadata_ or {}).get("proxy_enabled")

    @property
    def proxy_host(self) -> Optional[str]:
        return (self.metadata_ or {}).get("proxy_host")

    @property
    def proxy_port(self) -> Optional[int]:
        return (self.metadata_ or {}).get("proxy_port")

    @property
    def proxy_username(self) -> Optional[str]:
        return (self.metadata_ or {}).get("proxy_username")

    @property
    def proxy_password(self) -> Optional[str]:
        return (self.metadata_ or {}).get("proxy_password")
