"""
QueryPlan ORM 模型
查询计划 - 多步骤任务管理
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.sql import func
from ..core.database import Base


class QueryPlan(Base):
    """查询计划"""
    __tablename__ = "query_plan"

    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_id = Column(Integer, ForeignKey("agent.id", ondelete="CASCADE"), nullable=False, comment="Agent ID")
    user_query = Column(Text, nullable=False, comment="用户原始查询")
    plan_json = Column(JSON, nullable=False, comment="计划JSON（步骤列表）")
    status = Column(String(50), nullable=False, comment="状态: pending, running, completed, failed")
    result = Column(JSON, comment="执行结果")
    error = Column(Text, comment="错误信息")
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
