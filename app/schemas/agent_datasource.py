from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class AgentDatasourceCreate(BaseModel):
    """创建 Agent-Datasource 关联请求"""
    is_active: bool = Field(True, description="是否激活")


class AgentDatasourceResponse(BaseModel):
    """Agent-Datasource 关联响应"""
    id: int
    agent_id: int
    datasource_id: int
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AgentDatasourceWithDetails(AgentDatasourceResponse):
    """Agent-Datasource 关联响应（包含详情）"""
    datasource: Optional[dict] = None  # 包含 datasource 详情

    model_config = ConfigDict(from_attributes=True)


class AgentDatasourceListResponse(BaseModel):
    """Agent-Datasource 列表响应"""
    total: int
    items: list[AgentDatasourceWithDetails]
