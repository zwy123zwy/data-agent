"""ChatSession Pydantic Schema"""
from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import Optional
from datetime import datetime


# ═══════════════════════════════════════════════════════════════
# Request
# ═══════════════════════════════════════════════════════════════

class ChatSessionCreateRequest(BaseModel):
    """创建会话请求"""
    title: str = Field("新对话", description="会话标题")
    user_id: Optional[int] = Field(None, alias="userId", description="用户ID")

    model_config = ConfigDict(populate_by_name=True)


# ═══════════════════════════════════════════════════════════════
# Response
# ═══════════════════════════════════════════════════════════════

class ChatSessionResponse(BaseModel):
    """会话响应 """
    id: str
    agent_id: int = Field(..., alias="agentId")
    title: str
    status: str = "active"
    is_pinned: bool = Field(False, alias="isPinned")
    user_id: Optional[int] = Field(None, alias="userId")
    create_time: datetime = Field(..., alias="createTime")
    update_time: datetime = Field(..., alias="updateTime")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    @field_validator('is_pinned', mode='before')
    @classmethod
    def convert_pinned_to_bool(cls, v):
        """ORM 存储 int (0/1)，反序列化时转为 bool 对齐前端 boolean 类型"""
        if isinstance(v, int):
            return bool(v)
        return v
