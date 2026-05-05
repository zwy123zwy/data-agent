"""SessionUpdateEvent schema — 对齐 Java SessionUpdateEvent VO"""
from pydantic import BaseModel, Field, ConfigDict


class SessionUpdateEvent(BaseModel):
    """SSE 推送的会话更新事件 — 对齐 Java SessionUpdateEvent"""
    type: str = Field(..., alias="type")
    session_id: str = Field(..., alias="sessionId")
    title: str = Field(..., alias="title")

    model_config = ConfigDict(populate_by_name=True)

    @staticmethod
    def title_updated(session_id: str, title: str) -> "SessionUpdateEvent":
        return SessionUpdateEvent(type="title-updated", session_id=session_id, title=title)
