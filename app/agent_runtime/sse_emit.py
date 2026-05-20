# [阶段1-3] V2 SSE 事件构造辅助（Runner / Orchestrator / Agent 共用）

from __future__ import annotations

from app.agent_runtime.context import RuntimeContext
from app.agent_runtime.events import AgentSSEEvent
from app.agent_runtime.tools.base import ToolResult


def _artifact_refs(result: ToolResult) -> list[dict]:
    return [{"id": a.id, "type": a.type} for a in result.artifacts]


def emit_tool_call(
    ctx: RuntimeContext,
    agent_name: str,
    tool_name: str,
    summary: str,
) -> AgentSSEEvent:
    """[阶段1] 构造 tool.call 事件。"""
    return AgentSSEEvent.create_v2_only(
        run_id=ctx.run_id,
        event_type="tool.call",
        agent_id=ctx.agent_id,
        thread_id=ctx.thread_id,
        agent_name=agent_name,
        action=tool_name,
        status="running",
        summary=summary[:200],
    )


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
        run_id=ctx.run_id,
        event_type="text.delta",
        agent_id=ctx.agent_id,
        thread_id=ctx.thread_id,
        agent_name=agent_name,  # type: ignore[arg-type]
        action=action,
        status="running",
        summary="",
        text=delta,
        text_type=text_type,
    )


def emit_run_error(
    ctx: RuntimeContext,
    summary: str,
    *,
    error_code: str | None = None,
) -> AgentSSEEvent:
    """[阶段3] 不可恢复失败 — 供 Orchestrator 终止后续 Agent。"""
    return AgentSSEEvent.create_v2_only(
        run_id=ctx.run_id,
        event_type="error",
        agent_id=ctx.agent_id,
        thread_id=ctx.thread_id,
        status="error",
        summary=summary[:200],
        error=error_code or summary[:200],
    )


def emit_tool_result(
    ctx: RuntimeContext,
    agent_name: str,
    result: ToolResult,
) -> AgentSSEEvent:
    """[阶段1] 构造 tool.result 事件（含 V1 RESULT_SET 兼容字段）。"""
    return AgentSSEEvent.create_v2_only(
        run_id=ctx.run_id,
        event_type="tool.result",
        agent_id=ctx.agent_id,
        thread_id=ctx.thread_id,
        agent_name=agent_name,
        action=result.tool_name,
        status=result.status,
        summary=result.summary[:200],
        artifact_refs=_artifact_refs(result) or None,
        text_type=result.v1_text_type,
        text=result.v1_text or result.summary,
        error=result.summary if result.status == "error" else None,
    )
