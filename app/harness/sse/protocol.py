# [阶段1] SSE 构造所需的运行时上下文协议（Harness / agent_runtime 共用）

from __future__ import annotations

from typing import Any, Protocol


class RunContext(Protocol):
    """[阶段1] 任意 RuntimeContext 需提供的 run 标识字段。"""

    run_id: str
    agent_id: int
    thread_id: str


class ToolResultLike(Protocol):
    """[阶段1] tool.result 载荷来源（Harness / agent_runtime ToolResult 形状一致）。"""

    tool_name: str
    status: str
    summary: str
    v1_text_type: str
    v1_text: str | None
    artifacts: list[Any]
