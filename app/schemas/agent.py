from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class AgentBase(BaseModel):
    """Agent 基础模型"""
    name: str = Field(..., max_length=100, description="Agent名称")
    description: Optional[str] = Field(None, description="Agent描述")


class AgentCreate(AgentBase):
    """创建 Agent 请求"""
    category: Optional[str] = Field(None, max_length=100, description="分类")
    prompt: Optional[str] = Field(None, description="自定义Prompt")
    admin_id: Optional[int] = Field(None, description="管理员ID")


class AgentUpdate(BaseModel):
    """更新 Agent 请求"""
    name: Optional[str] = Field(None, max_length=100, description="Agent名称")
    description: Optional[str] = Field(None, description="Agent描述")
    status: Optional[str] = Field(None, pattern="^(draft|published|offline)$", description="状态")
    avatar: Optional[str] = Field(None, max_length=255, description="头像URL")
    tags: Optional[str] = Field(None, max_length=500, description="标签")
    category: Optional[str] = Field(None, max_length=100, description="分类")
    prompt: Optional[str] = Field(None, description="自定义Prompt")
    admin_id: Optional[int] = Field(None, description="管理员ID")


class AgentResponse(AgentBase):
    """Agent 响应 — camelCase 对齐前端/Java"""
    id: int
    status: str
    avatar: Optional[str] = None
    tags: Optional[str] = None
    api_key: Optional[str] = Field(None, alias="apiKey", description="API Key(脱敏)")
    api_key_enabled: bool = Field(False, alias="apiKeyEnabled")
    category: Optional[str] = None
    prompt: Optional[str] = None
    admin_id: Optional[int] = Field(None, alias="adminId")
    human_review_enabled: bool = Field(False, alias="humanReviewEnabled", description="是否启用人工审核")
    created_at: datetime = Field(..., alias="createTime")
    updated_at: datetime = Field(..., alias="updateTime")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class AgentListResponse(BaseModel):
    """Agent 列表响应"""
    total: int
    items: list[AgentResponse]
