# [阶段4] agent_artifact 表 — Artifact 引用落库

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AgentArtifactRecord(Base):
    """[阶段4] Artifact 持久化（content 可截断存摘要）。"""

    __tablename__ = "agent_artifact"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("agent_run.id", ondelete="CASCADE"), nullable=False, index=True
    )
    artifact_type: Mapped[str] = mapped_column(String(32), nullable=False)
    content_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    create_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
