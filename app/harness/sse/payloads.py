# [阶段1] V2 SSE 事件字段构造（纯 dict，供 HarnessSSEEvent / AgentSSEEvent 复用）

from __future__ import annotations

from typing import Any

from app.harness.sse.artifacts import artifact_refs_from_artifacts
from app.harness.sse.constants import truncate_summary
from app.harness.sse.protocol import RunContext, ToolResultLike
from app.harness.types.events import HarnessEventType

# 默认 node/agent 展示名
DEFAULT_AGENT_NAME = "Harness"


def _base_fields(
    ctx: RunContext,
    event_type: HarnessEventType,
    *,
    agent_name: str | None = None,
    action: str | None = None,
    status: str | None = None,
    summary: str | None = None,
    text: str | None = None,
    text_type: str = "TEXT",
    artifact_refs: list[dict[str, str]] | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    """[阶段1] HarnessSSEEvent.create / AgentSSEEvent.create_v2_only 共用字段包。"""
    return {
        "run_id": ctx.run_id,
        "event_type": event_type,
        "agent_id": ctx.agent_id,
        "thread_id": ctx.thread_id,
        "agent_name": agent_name,
        "action": action,
        "status": status,
        "summary": truncate_summary(summary) if summary else summary,
        "text": text,
        "text_type": text_type,
        "artifact_refs": artifact_refs,
        "error": error,
    }


def think_payload(
    ctx: RunContext,
    *,
    summary: str,
    text: str = "",
    action: str,
    agent_name: str | None = None,
) -> dict[str, Any]:
    """[阶段1] agent.think 字段包。"""
    body = text or summary
    return _base_fields(
        ctx,
        "agent.think",
        agent_name=agent_name,
        action=action,
        status="ok",
        summary=summary,
        text=body,
    )


def text_delta_payload(
    ctx: RunContext,
    delta: str,
    *,
    agent_name: str = DEFAULT_AGENT_NAME,
    action: str | None = None,
    text_type: str = "TEXT",
) -> dict[str, Any]:
    """[阶段1] text.delta 字段包。"""
    return _base_fields(
        ctx,
        "text.delta",
        agent_name=agent_name,
        action=action,
        status="running",
        summary="",
        text=delta,
        text_type=text_type,
    )


def tool_call_payload(
    ctx: RunContext,
    agent_name: str,
    tool_name: str,
    summary: str,
) -> dict[str, Any]:
    """[阶段1] tool.call 字段包。"""
    return _base_fields(
        ctx,
        "tool.call",
        agent_name=agent_name,
        action=tool_name,
        status="running",
        summary=summary,
    )


def tool_result_payload(
    ctx: RunContext,
    agent_name: str,
    result: ToolResultLike,
) -> dict[str, Any]:
    """[阶段1] tool.result 字段包（含 V1 RESULT_SET / SQL 兼容）。"""
    refs = artifact_refs_from_artifacts(result.artifacts) or None
    return _base_fields(
        ctx,
        "tool.result",
        agent_name=agent_name,
        action=result.tool_name,
        status=result.status,
        summary=result.summary,
        artifact_refs=refs,
        text_type=result.v1_text_type,
        text=result.v1_text or result.summary,
        error=result.summary if result.status == "error" else None,
    )


def run_error_payload(
    ctx: RunContext,
    summary: str,
    *,
    error_code: str | None = None,
) -> dict[str, Any]:
    """[阶段1] error 字段包。"""
    code = error_code or truncate_summary(summary)
    return _base_fields(
        ctx,
        "error",
        status="error",
        summary=summary,
        error=code,
        text=summary,
    )


def preflight_error_payload(
    *,
    run_id: str,
    agent_id: int,
    thread_id: str,
    code: str,
    summary: str,
) -> dict[str, Any]:
    """[阶段1] Preflight 阻断时尚无完整 RuntimeContext。"""
    return {
        "run_id": run_id,
        "event_type": "error",
        "agent_id": agent_id,
        "thread_id": thread_id,
        "status": "error",
        "summary": truncate_summary(summary),
        "error": code,
        "text": summary,
    }


def agent_execution_started_payload(
    ctx: RunContext,
    *,
    run_profile: str = "smart_query",
    action: str,
) -> dict[str, Any]:
    """[阶段1] agent.execution.started 字段包。"""
    summary = "开始执行数据分析 Agent"
    return _base_fields(
        ctx,
        "agent.execution.started",
        agent_name=DEFAULT_AGENT_NAME,
        action=action,
        status="running",
        summary=summary,
        text=f"route=agent, profile={run_profile}",
    )


def tools_available_payload(
    ctx: RunContext,
    tool_names: list[str],
) -> dict[str, Any]:
    """[阶段1] tools.available 字段包。"""
    joined = ",".join(tool_names)
    summary = f"可用工具: {joined}" if tool_names else "无可用工具"
    return _base_fields(
        ctx,
        "tools.available",
        status="ok",
        summary=summary,
        text=joined,
    )
