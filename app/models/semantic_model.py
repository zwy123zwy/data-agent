"""
SemanticModel ORM 模型
语义模型 - 业务术语到数据库字段的映射
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.sql import func
from ..core.database import Base


class SemanticModel(Base):
    """语义模型"""
    __tablename__ = "semantic_model"

    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_id = Column(Integer, ForeignKey("agent.id", ondelete="CASCADE"), nullable=False, comment="Agent ID")
    datasource_id = Column(Integer, ForeignKey("datasource.id", ondelete="CASCADE"), nullable=False, comment="数据源ID")
    table_name = Column(String(100), nullable=False, comment="表名")
    column_name = Column(String(100), comment="字段名（NULL表示表级别）")
    business_name = Column(String(200), nullable=False, comment="业务名称")
    description = Column(Text, comment="业务描述")
    synonyms = Column(JSON, comment="同义词列表")
    sample_values = Column(JSON, comment="示例值")
    metadata_ = Column("metadata", JSON, comment="元数据")
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
