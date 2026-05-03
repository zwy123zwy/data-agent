"""AgentPresetQuestion Pydantic Schema"""
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime


class AgentPresetQuestionCreate(BaseModel):
    question: str
    sort_order: int = 0
    is_active: bool = True


class AgentPresetQuestionResponse(BaseModel):
    id: int
    agent_id: int
    question: str
    sort_order: int = 0
    is_active: bool = False
    create_time: datetime
    update_time: datetime

    model_config = ConfigDict(from_attributes=True)
