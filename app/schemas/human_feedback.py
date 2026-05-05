"""HumanFeedback Pydantic Schema — 对齐 Java HumanFeedback"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime


# ═══════════════════════════════════════════════════════════════
# 基类
# ═══════════════════════════════════════════════════════════════

class HumanFeedbackBase(BaseModel):
    """人工反馈公共字段"""
    workflow_id: str = Field(..., alias="workflowId", max_length=100, description="工作流ID")
    node_name: str = Field(..., alias="nodeName", max_length=100, description="节点名称")
    content: str = Field(..., description="待审批内容")

    model_config = ConfigDict(populate_by_name=True)


# ═══════════════════════════════════════════════════════════════
# Request
# ═══════════════════════════════════════════════════════════════

class HumanFeedbackCreateRequest(HumanFeedbackBase):
    """创建人工反馈请求"""
    agent_id: int = Field(..., alias="agentId", description="Agent ID")


class HumanFeedbackSubmitRequest(BaseModel):
    """提交反馈请求"""
    action: str = Field(..., description="用户操作: approve, reject, modify")
    comment: Optional[str] = Field(None, description="用户评论")
    modified_content: Optional[str] = Field(None, alias="modifiedContent", description="修改后的内容")

    model_config = ConfigDict(populate_by_name=True)


# ═══════════════════════════════════════════════════════════════
# Response
# ═══════════════════════════════════════════════════════════════

class HumanFeedbackResponse(HumanFeedbackBase):
    """人工反馈响应 — camelCase 对齐 Java"""
    id: int
    agent_id: int = Field(..., alias="agentId")
    action: Optional[str] = None
    comment: Optional[str] = None
    modified_content: Optional[str] = Field(None, alias="modifiedContent")
    status: str
    created_at: datetime = Field(..., alias="createTime")
    updated_at: datetime = Field(..., alias="updateTime")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
