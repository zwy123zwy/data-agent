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
from app.harness.types.observation import Observation

logger = logging.getLogger(__name__)


class ToolResult(BaseModel):
    """[阶段2] Tool 统一返回结构。
    
    Attributes:
        status: 工具执行状态，"ok"表示成功，"error"表示失败
        tool_name: 执行的工具名称
        data: 工具执行结果数据
        summary: 工具执行结果摘要
        artifacts: 工具执行产生的工件列表
        error_code: 错误代码（如果有的话）
        error_severity: 错误严重程度，"retryable"可重试，"fatal"致命错误
        duration_ms: 工具执行耗时（毫秒）
        tokens_used: 使用的token数量
        v1_text: 版本1文本内容
        v1_text_type: 版本1文本类型，默认为"TEXT"
    """

    status: Literal["ok", "error"]
    tool_name: str
    # TODO: 工具返回数据类型,太宽泛了
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

    def to_observation(self) -> Observation:
        """[阶段4] 转为 Agent 循环可消费的 Observation。"""
        status: Literal["ok", "error", "partial"] = (
            "ok" if self.status == "ok" else "error"
        )
        structured = self.data if isinstance(self.data, dict) else None
        return Observation(
            tool_name=self.tool_name,
            status=status,
            summary=self.summary or "",
            structured=structured,
            error_code=self.error_code,
            error_severity=self.error_severity,
            duration_ms=self.duration_ms,
        )


def _tool_timeout_seconds() -> float:
    """获取单个工具执行的超时时间（秒）。
    
    Returns:
        float: 超时时间，最小为5秒，默认为120秒
    """
    # TODO: 超时时间硬编码不合适吧， 应该让工具自己定义，或者在配置里定义不同工具的超时时间
    return max(5.0, float(getattr(settings, "harness_tool_timeout_seconds", 120)))


class BaseTool(ABC):
    """[阶段2] Harness Tool 抽象基类：读取RuntimeContext，写入workflow状态。
    
    这是一个抽象基类，定义了所有Harness工具的基本接口和行为。
    """

    name: str

    @abstractmethod
    async def run(
        self,
        ctx: RuntimeContext,
        state: dict[str, Any],
        db: AsyncSession,
    ) -> ToolResult:
        """执行工具的核心逻辑。
        
        Args:
            ctx: 运行时上下文，包含执行环境信息
            state: 当前工作流状态字典
            db: 异步数据库会话
        
        Returns:
            ToolResult: 包含执行结果的ToolResult对象
        """

    async def timed_run(
        self,
        ctx: RuntimeContext,
        state: dict[str, Any],
        db: AsyncSession,
    ) -> ToolResult:
        """带耗时统计与超时保护的工具执行入口。
        
        此方法包装了run方法，提供超时控制和执行时间统计功能。
        
        Args:
            ctx: 运行时上下文，包含执行环境信息
            state: 当前工作流状态字典
            db: 异步数据库会话
        
        Returns:
            ToolResult: 包含执行结果的ToolResult对象，包含执行时间等额外信息
        """
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
