from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class QueryRequest(BaseModel):
    """查询请求"""
    agent_id: int = Field(..., description="Agent ID")
    query: str = Field(..., min_length=1, description="用户问题")


class QueryResponse(BaseModel):
    """查询响应"""
    intent: str
    sql: Optional[str] = None
    result: Optional[List[Dict[str, Any]]] = None
    report: Optional[str] = None
    error: Optional[str] = None
