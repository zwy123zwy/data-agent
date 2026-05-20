# [阶段1] Tool 基类与 ToolResult — Harness #1 统一工具契约

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.agent_runtime.artifacts import Artifact
from app.agent_runtime.context import RuntimeContext


class ToolResult(BaseModel):
    """[阶段1] 所有 V2 Tool 的返回类型，禁止裸 dict。"""

    status: Literal["ok", "error"]
    tool_name: str
    data: Any = None
    summary: str = ""
    artifacts: list[Artifact] = Field(default_factory=list)
    error_code: str | None = None
    error_severity: Literal["retryable", "fatal"] | None = None
    duration_ms: int = 0
    tokens_used: int = 0
    # V1 前端兼容：部分 Tool 需带 RESULT_SET / SQL 文本
    v1_text: str | None = None
    v1_text_type: str = "TEXT"

    model_config = ConfigDict(extra="forbid")


class BaseTool(ABC):
    """[阶段1] Tool 抽象基类：输入 RuntimeContext + 可变 workflow state 补丁。"""

    name: str

    @abstractmethod
    async def run(
        self,
        ctx: RuntimeContext,
        state: dict[str, Any],
        db: Any,
    ) -> ToolResult:
        """执行工具；state 为 V1 WorkflowState 字典，可就地更新。"""

    async def _timed_run(
        self,
        ctx: RuntimeContext,
        state: dict[str, Any],
        db: Any,
    ) -> ToolResult:
        start = time.perf_counter()
        result = await self.run(ctx, state, db)
        result.duration_ms = int((time.perf_counter() - start) * 1000)
        if not result.tool_name:
            result.tool_name = self.name
        return result
