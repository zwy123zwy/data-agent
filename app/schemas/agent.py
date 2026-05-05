"""Agent Schema — 对齐 Java Agent Entity + 前端 camelCase"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


# ═══════════════════════════════════════════════════════════════
# 基类
# ═══════════════════════════════════════════════════════════════

class AgentBase(BaseModel):
    """Agent 公共字段"""
    name: str = Field(..., max_length=100, description="Agent名称")
    description: Optional[str] = Field(None, description="Agent描述")
    avatar: Optional[str] = Field(None, max_length=255, description="头像URL")
    tags: Optional[str] = Field(None, max_length=500, description="标签")
    category: Optional[str] = Field(None, max_length=100, description="分类")
    prompt: Optional[str] = Field(None, description="自定义Prompt")
    admin_id: Optional[int] = Field(None, alias="adminId", description="管理员ID")

    model_config = ConfigDict(populate_by_name=True)


# ═══════════════════════════════════════════════════════════════
# Request
# ═══════════════════════════════════════════════════════════════

class AgentCreateRequest(AgentBase):
    """创建 Agent — 对齐 Java POST /api/agent"""
    pass


class AgentUpdateRequest(AgentBase):
    """更新 Agent — 对齐 Java PUT /api/agent/{id}"""
    name: Optional[str] = Field(None, max_length=100, description="Agent名称")
    description: Optional[str] = Field(None, description="Agent描述")
    status: Optional[str] = Field(None, pattern="^(draft|published|offline)$", description="状态")
    human_review_enabled: Optional[int] = Field(None, alias="humanReviewEnabled", description="人工审核: 0/1")


# ═══════════════════════════════════════════════════════════════
# Response
# ═══════════════════════════════════════════════════════════════

class AgentResponse(AgentBase):
    """Agent 响应 — camelCase 对齐前端"""
    id: int
    status: str
    api_key: Optional[str] = Field(None, alias="apiKey", description="API Key(脱敏)")
    api_key_enabled: int = Field(0, alias="apiKeyEnabled", description="API Key启用: 0/1")
    human_review_enabled: int = Field(0, alias="humanReviewEnabled", description="人工审核: 0/1")
    create_time: datetime = Field(..., alias="createTime")
    update_time: datetime = Field(..., alias="updateTime")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


# ========== 兼容别名 ==========
AgentCreate = AgentCreateRequest
AgentUpdate = AgentUpdateRequest
