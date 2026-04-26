"""
HumanFeedback Pydantic Schema
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class HumanFeedbackBase(BaseModel):
    """人工反馈基础 Schema"""
    workflow_id: str = Field(..., max_length=100, description="工作流ID")
    node_name: str = Field(..., max_length=100, description="节点名称")
    content: str = Field(..., description="待审批内容")


class HumanFeedbackCreate(HumanFeedbackBase):
    """创建人工反馈请求"""
    agent_id: int = Field(..., description="Agent ID")


class HumanFeedbackSubmit(BaseModel):
    """提交反馈请求"""
    action: str = Field(..., description="用户操作: approve, reject, modify")
    comment: Optional[str] = Field(None, description="用户评论")
    modified_content: Optional[str] = Field(None, description="修改后的内容")


class HumanFeedbackResponse(HumanFeedbackBase):
    """人工反馈响应"""
    id: int
    agent_id: int
    action: Optional[str] = None
    comment: Optional[str] = None
    modified_content: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
