"""ChatMessage Pydantic Schema — 对齐 Java ChatMessage"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, Any
from datetime import datetime


# ═══════════════════════════════════════════════════════════════
# Request
# ═══════════════════════════════════════════════════════════════

class ChatMessageCreateRequest(BaseModel):
    """创建消息请求 — 对齐 Java ChatMessageDTO"""
    role: str = Field(..., pattern="^(user|assistant|system)$")
    content: str = Field(..., description="消息内容")
    message_type: str = Field("text", alias="messageType", pattern="^(text|sql|result|error)$")
    metadata: Optional[Dict[str, Any]] = Field(None, description="元数据")
    title_needed: bool = Field(False, alias="titleNeeded", description="是否自动生成标题")

    model_config = ConfigDict(populate_by_name=True)


# ═══════════════════════════════════════════════════════════════
# Response
# ═══════════════════════════════════════════════════════════════

class ChatMessageResponse(BaseModel):
    """消息响应 — camelCase 对齐 Java ChatMessage"""
    id: int
    session_id: str = Field(..., alias="sessionId")
    role: str
    content: str
    message_type: str = Field("text", alias="messageType")
    metadata: Optional[Dict[str, Any]] = Field(None, alias="metadata_")
    create_time: datetime = Field(..., alias="createTime")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
