"""ChatSession Pydantic Schema — 对齐 Java ChatSession"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime


# ═══════════════════════════════════════════════════════════════
# Request
# ═══════════════════════════════════════════════════════════════

class ChatSessionCreateRequest(BaseModel):
    """创建会话请求 — 对齐 Java ChatController.createSession"""
    title: str = Field("新对话", description="会话标题")
    user_id: Optional[int] = Field(None, alias="userId", description="用户ID")

    model_config = ConfigDict(populate_by_name=True)


# ═══════════════════════════════════════════════════════════════
# Response
# ═══════════════════════════════════════════════════════════════

class ChatSessionResponse(BaseModel):
    """会话响应 — camelCase 对齐 Java ChatSession"""
    id: str
    agent_id: int = Field(..., alias="agentId")
    title: str
    status: str = "active"
    is_pinned: int = Field(0, alias="isPinned")
    user_id: Optional[int] = Field(None, alias="userId")
    create_time: datetime = Field(..., alias="createTime")
    update_time: datetime = Field(..., alias="updateTime")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
