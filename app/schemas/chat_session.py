"""ChatSession Pydantic Schema"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime


class ChatSessionCreate(BaseModel):
    agent_id: int
    title: str = "新对话"
    user_id: Optional[int] = None


class ChatSessionResponse(BaseModel):
    id: str
    agent_id: int
    title: str
    status: str = "active"
    is_pinned: bool = False
    user_id: Optional[int] = None
    create_time: datetime
    update_time: datetime

    model_config = ConfigDict(from_attributes=True)
