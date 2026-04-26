"""
QueryPlan Pydantic Schema
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class PlanStatus(str, Enum):
    """计划状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class StepType(str, Enum):
    """步骤类型"""
    SQL_QUERY = "sql_query"
    PYTHON_ANALYSIS = "python_analysis"
    REPORT = "report"


class PlanStep(BaseModel):
    """计划步骤"""
    id: int = Field(..., description="步骤ID")
    type: StepType = Field(..., description="步骤类型")
    description: str = Field(..., description="步骤描述")
    depends_on: List[int] = Field(default_factory=list, description="依赖的步骤ID列表")
    sql: Optional[str] = Field(None, description="SQL语句（sql_query类型）")
    code: Optional[str] = Field(None, description="Python代码（python_analysis类型）")
    params: Optional[Dict[str, Any]] = Field(None, description="其他参数")


class QueryPlanCreate(BaseModel):
    """创建查询计划请求"""
    user_query: str = Field(..., description="用户查询")
    steps: List[PlanStep] = Field(..., description="计划步骤列表")


class QueryPlanResponse(BaseModel):
    """查询计划响应"""
    id: int
    agent_id: int
    user_query: str
    plan_json: Dict[str, Any]
    status: PlanStatus
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ExecutePlanResponse(BaseModel):
    """执行计划响应"""
    simple: bool = Field(..., description="是否为简单查询")
    message: str = Field(..., description="提示消息")
    plan: Optional[QueryPlanResponse] = Field(None, description="计划详情（复杂查询时）")


class GeneratePlanRequest(BaseModel):
    """生成计划请求"""
    query: str = Field(..., description="用户查询")


class GeneratePlanResponse(BaseModel):
    """生成计划响应"""
    plan: Dict[str, Any] = Field(..., description="生成的计划")
    steps: List[PlanStep] = Field(..., description="步骤列表")


class ExecutePlanRequest(BaseModel):
    """执行计划请求"""
    query: str = Field(..., description="用户查询")
    auto_execute: bool = Field(True, description="是否自动执行")


class QueryPlanListResponse(BaseModel):
    """查询计划列表响应"""
    items: List[QueryPlanResponse]
    total: int
    page: int
    size: int
    pages: int
