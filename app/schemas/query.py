from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any


class QueryRequest(BaseModel):
    """查询请求 — camelCase 对齐前端/Java"""
    agent_id: int = Field(..., alias="agentId", description="Agent ID")
    query: str = Field(..., min_length=1, description="用户问题")
    workflow_id: Optional[str] = Field(None, alias="workflowId", description="工作流ID（用于恢复）")
    human_feedback: bool = Field(False, alias="humanFeedback", description="是否启用人工反馈")
    human_feedback_content: Optional[str] = Field(None, alias="humanFeedbackContent", description="人工反馈内容（恢复时传入）")
    rejected_plan: bool = Field(False, alias="rejectedPlan", description="是否拒绝当前方案")
    nl2sql_only: bool = Field(False, alias="nl2sqlOnly", description="仅 NL2SQL 模式")

    model_config = ConfigDict(populate_by_name=True)


class QueryResponse(BaseModel):
    """查询响应"""
    intent: str
    sql: Optional[str] = None
    result: Optional[List[Dict[str, Any]]] = None
    report: Optional[str] = None
    error: Optional[str] = None
    workflow_id: Optional[str] = None
    status: Optional[str] = None
