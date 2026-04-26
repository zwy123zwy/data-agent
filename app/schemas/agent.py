from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class AgentBase(BaseModel):
    """Agent 基础模型"""
    name: str = Field(..., max_length=100, description="Agent名称")
    description: Optional[str] = Field(None, description="Agent描述")


class AgentCreate(AgentBase):
    """创建 Agent 请求"""
    pass


class AgentUpdate(BaseModel):
    """更新 Agent 请求"""
    name: Optional[str] = Field(None, max_length=100, description="Agent名称")
    description: Optional[str] = Field(None, description="Agent描述")
    status: Optional[str] = Field(None, pattern="^(draft|published|offline)$", description="状态")
    avatar: Optional[str] = Field(None, max_length=255, description="头像URL")
    tags: Optional[str] = Field(None, max_length=500, description="标签")


class AgentResponse(AgentBase):
    """Agent 响应"""
    id: int
    status: str
    avatar: Optional[str] = None
    tags: Optional[str] = None
    api_key_enabled: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AgentListResponse(BaseModel):
    """Agent 列表响应"""
    total: int
    items: list[AgentResponse]
