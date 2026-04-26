"""
HumanFeedback ORM 模型
人工反馈记录
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from ..core.database import Base


class HumanFeedback(Base):
    """人工反馈记录"""
    __tablename__ = "human_feedback"

    id = Column(Integer, primary_key=True, autoincrement=True)
    workflow_id = Column(String(100), nullable=False, comment="工作流ID")
    agent_id = Column(Integer, ForeignKey("agent.id", ondelete="CASCADE"), nullable=False, comment="Agent ID")
    node_name = Column(String(100), nullable=False, comment="节点名称")
    content = Column(Text, nullable=False, comment="待审批内容")
    action = Column(String(50), comment="用户操作: approve, reject, modify")
    comment = Column(Text, comment="用户评论")
    modified_content = Column(Text, comment="修改后的内容")
    status = Column(String(50), nullable=False, default="pending", comment="状态: pending, approved, rejected")
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
