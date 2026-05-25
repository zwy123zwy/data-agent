# [阶段1-3] V2 SSE 事件构造 — 复用 harness.sse.payloads，产出 AgentSSEEvent

from __future__ import annotations

from app.agent_runtime.context import RuntimeContext
from app.agent_runtime.events import AgentSSEEvent
from app.agent_runtime.tools.base import ToolResult
from app.harness.sse.payloads import (
    run_error_payload,
    text_delta_payload,
    tool_call_payload,
    tool_result_payload,
)


def emit_tool_call(
    ctx: RuntimeContext,
    agent_name: str,
    tool_name: str,
    summary: str,
) -> AgentSSEEvent:
    """[阶段1] 构造 tool.call 事件。"""
    return AgentSSEEvent.create_v2_only(**tool_call_payload(ctx, agent_name, tool_name, summary))


def emit_text_delta(
    ctx: RuntimeContext,
    agent_name: str,
    delta: str,
    *,
    text_type: str = "TEXT",
    action: str | None = None,
) -> AgentSSEEvent:
    """[阶段5] LLM 流式片段 — 前端逐字渲染。"""
    return AgentSSEEvent.create_v2_only(
        **text_delta_payload(
            ctx,
            delta,
            agent_name=agent_name,
            action=action,
            text_type=text_type,
        ),
    )


def emit_run_error(
    ctx: RuntimeContext,
    summary: str,
    *,
    error_code: str | None = None,
) -> AgentSSEEvent:
    """[阶段3] 不可恢复失败 — 供 Orchestrator 终止后续 Agent。"""
    return AgentSSEEvent.create_v2_only(**run_error_payload(ctx, summary, error_code=error_code))


def emit_tool_result(
    ctx: RuntimeContext,
    agent_name: str,
    result: ToolResult,
) -> AgentSSEEvent:
    """[阶段1] 构造 tool.result 事件（含 V1 RESULT_SET 兼容字段）。"""
    return AgentSSEEvent.create_v2_only(**tool_result_payload(ctx, agent_name, result))
