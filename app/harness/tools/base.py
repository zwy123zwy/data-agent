# [阶段2] Harness Tool 基类与 ToolResult（独立于 agent_runtime.tools.base）
# [Harness: Tool Access #1]
# M2.5: timed_run 增加 asyncio 超时（T-05）

from __future__ import annotations

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.harness.types.artifacts import Artifact
from app.harness.types.context import RuntimeContext

logger = logging.getLogger(__name__)


class ToolResult(BaseModel):
    """[阶段2] Tool 统一返回结构。"""

    status: Literal["ok", "error"]
    tool_name: str
    data: Any = None
    summary: str = ""
    artifacts: list[Artifact] = Field(default_factory=list)
    error_code: str | None = None
    error_severity: Literal["retryable", "fatal"] | None = None
    duration_ms: int = 0
    tokens_used: int = 0
    v1_text: str | None = None
    v1_text_type: str = "TEXT"

    model_config = ConfigDict(extra="forbid")


def _tool_timeout_seconds() -> float:
    """[阶段2] 单工具执行超时秒数（M2.5）。"""
    return max(5.0, float(getattr(settings, "harness_tool_timeout_seconds", 120)))


class BaseTool(ABC):
    """[阶段2] Harness Tool 抽象：读 RuntimeContext，写 workflow state。"""

    name: str

    @abstractmethod
    async def run(
        self,
        ctx: RuntimeContext,
        state: dict[str, Any],
        db: AsyncSession,
    ) -> ToolResult:
        """[阶段2] 执行工具逻辑。"""

    async def timed_run(
        self,
        ctx: RuntimeContext,
        state: dict[str, Any],
        db: AsyncSession,
    ) -> ToolResult:
        """[阶段2] 带耗时与超时保护的执行入口。"""
        start = time.perf_counter()
        timeout = _tool_timeout_seconds()
        try:
            result = await asyncio.wait_for(
                self.run(ctx, state, db),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            logger.warning(
                "[阶段2][Tool] %s 超时 (%.0fs)",
                self.name,
                timeout,
            )
            result = ToolResult(
                status="error",
                tool_name=self.name,
                summary=f"工具执行超时（{int(timeout)}s）",
                error_code="TOOL_TIMEOUT",
                error_severity="retryable",
            )
        result.duration_ms = int((time.perf_counter() - start) * 1000)
        if not result.tool_name:
            result.tool_name = self.name
        return result
