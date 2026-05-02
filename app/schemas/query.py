from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class QueryRequest(BaseModel):
    """查询请求"""
    agent_id: int = Field(..., description="Agent ID")
    query: str = Field(..., min_length=1, description="用户问题")
    workflow_id: Optional[str] = Field(None, description="工作流ID（用于恢复）")
    human_feedback: bool = Field(False, description="是否启用人工反馈")
    human_feedback_content: Optional[str] = Field(None, description="人工反馈内容（恢复时传入）")
    rejected_plan: bool = Field(False, description="是否拒绝当前方案")
    nl2sql_only: bool = Field(False, description="仅 NL2SQL 模式")


class QueryResponse(BaseModel):
    """查询响应"""
    intent: str
    sql: Optional[str] = None
    result: Optional[List[Dict[str, Any]]] = None
    report: Optional[str] = None
    error: Optional[str] = None
    workflow_id: Optional[str] = None
    status: Optional[str] = None
