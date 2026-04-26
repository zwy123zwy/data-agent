"""
Knowledge ORM 模型
"""
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.sql import func
from ..core.database import Base


class Knowledge(Base):
    """知识库模型"""
    __tablename__ = "knowledge"

    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_id = Column(Integer, ForeignKey("agent.id", ondelete="CASCADE"), nullable=False, comment="Agent ID")
    title = Column(String(200), nullable=False, comment="知识标题")
    content = Column(Text, nullable=False, comment="知识内容")
    type = Column(String(50), nullable=False, comment="知识类型: business_term, query_example, business_rule")
    embedding_id = Column(String(100), comment="向量ID（Chroma）")
    metadata_ = Column("metadata", JSON, comment="元数据")
    enabled = Column(Boolean, default=True, nullable=False, comment="是否启用")
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
