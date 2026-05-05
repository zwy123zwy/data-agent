"""
Knowledge ORM 模型
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON, BigInteger
from sqlalchemy.sql import func
from ..core.database import Base


class Knowledge(Base):
    """知识库模型 - 对齐 Java AgentKnowledge"""
    __tablename__ = "agent_knowledge"

    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_id = Column(Integer, ForeignKey("agent.id", ondelete="CASCADE"), nullable=False, comment="Agent ID")
    title = Column(String(200), nullable=False, comment="知识标题")
    content = Column(Text, nullable=False, comment="知识内容")
    type = Column(String(50), nullable=False, comment="知识类型: DOCUMENT/QA/FAQ（对齐Java KnowledgeType）")
    question = Column(Text, comment="FAQ/QA 问题（对齐Java）")
    is_recall = Column(Integer, default=1, comment="业务状态: 1=召回, 0=非召回（对齐Java）")
    embedding_id = Column(String(100), comment="向量ID（Chroma）")
    embedding_status = Column(String(20), default="PENDING", comment="向量化状态: PENDING/PROCESSING/COMPLETED/FAILED（对齐Java）")
    error_msg = Column(Text, comment="操作失败的错误信息（对齐Java）")
    metadata_ = Column("metadata", JSON, comment="元数据")
    enabled = Column(Integer, default=1, nullable=False, comment="是否启用: 0/1")

    # 文件管理字段（对齐Java）
    source_filename = Column(String(255), comment="源文件名（对齐Java）")
    file_path = Column(String(500), comment="文件路径（对齐Java）")
    file_size = Column(BigInteger, comment="文件大小（字节，对齐Java）")
    file_type = Column(String(50), comment="文件类型（对齐Java）")
    splitter_type = Column(String(50), default="token", comment="分块策略: token/recursive（对齐Java）")

    # 软删除（对齐Java）
    is_deleted = Column(Integer, default=0, comment="0=未删除, 1=已删除（对齐Java）")
    is_resource_cleaned = Column(Integer, default=0, comment="0=物理资源未清理, 1=物理资源已清理（对齐Java）")

    created_time = Column(DateTime, server_default=func.now(), nullable=False)
    updated_time = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
