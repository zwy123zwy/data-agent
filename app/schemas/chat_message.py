"""ChatMessage Pydantic Schema"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, Any
from datetime import datetime


class ChatMessageCreate(BaseModel):
    session_id: str
    role: str = Field(..., pattern="^(user|assistant|system)$")
    content: str
    message_type: str = Field("text", pattern="^(text|sql|result|error)$")
    metadata: Optional[Dict[str, Any]] = Field(None, alias="metadata_")


class ChatMessageResponse(BaseModel):
    id: int
    session_id: str
    role: str
    content: str
    message_type: str = "text"
    metadata: Optional[Dict[str, Any]] = Field(None, alias="metadata_")
    create_time: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
