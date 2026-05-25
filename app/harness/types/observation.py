# [阶段4] Observation — Agent 循环对外暴露的工具执行摘要（M4 里程碑）

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class Observation(BaseModel):
    """[阶段4] 单次 Tool 执行的结构化观察，供 Agent / Answer 读取。"""

    tool_name: str
    status: Literal["ok", "error", "partial"]
    summary: str
    structured: dict | None = None
    error_code: str | None = None
    error_severity: Literal["retryable", "fatal"] | None = None
    duration_ms: int = 0
    next_hint: str | None = None

    model_config = ConfigDict(extra="forbid")
