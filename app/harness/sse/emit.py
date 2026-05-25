# [阶段2] Harness SSE 事件构造：薄封装 payloads → HarnessSSEEvent
# [Harness: Observability #6]

from __future__ import annotations

from app.harness.sse.actions import HarnessSseAction
from app.harness.sse.payloads import (
    agent_execution_started_payload,
    preflight_error_payload,
    run_error_payload,
    text_delta_payload,
    think_payload,
    tool_call_payload,
    tool_result_payload,
    tools_available_payload,
)
from app.harness.sse.protocol import RunContext
from app.harness.tools.base import ToolResult
from app.harness.types.context import RuntimeContext
from app.harness.types.events import HarnessSSEEvent


def emit_think(
    ctx: RuntimeContext,
    *,
    summary: str,
    text: str = "",
    action: str = HarnessSseAction.THINK_DEFAULT,
) -> HarnessSSEEvent:
    """[阶段2] 思考区 agent.think。"""
    return HarnessSSEEvent.create(**think_payload(ctx, summary=summary, text=text, action=action))


def emit_text_delta(
    ctx: RuntimeContext,
    delta: str,
    *,
    agent_name: str = "Harness",
    action: str = HarnessSseAction.REPLY,
) -> HarnessSSEEvent:
    """[阶段2] 正文区 text.delta。"""
    return HarnessSSEEvent.create(
        **text_delta_payload(ctx, delta, agent_name=agent_name, action=action),
    )


def emit_error(
    ctx: RuntimeContext | None,
    *,
    agent_id: int,
    thread_id: str,
    run_id: str,
    code: str,
    summary: str,
) -> HarnessSSEEvent:
    """[阶段2] Preflight / Gateway 阻断错误。"""
    _ = ctx
    return HarnessSSEEvent.create(
        **preflight_error_payload(
            run_id=run_id,
            agent_id=agent_id,
            thread_id=thread_id,
            code=code,
            summary=summary,
        ),
    )


def emit_tool_call(
    ctx: RuntimeContext,
    agent_name: str,
    tool_name: str,
    summary: str,
) -> HarnessSSEEvent:
    """[阶段2] tool.call。"""
    return HarnessSSEEvent.create(**tool_call_payload(ctx, agent_name, tool_name, summary))


def emit_tool_result(
    ctx: RuntimeContext,
    agent_name: str,
    result: ToolResult,
) -> HarnessSSEEvent:
    """[阶段2] tool.result（含 V1 RESULT_SET 兼容字段）。"""
    return HarnessSSEEvent.create(**tool_result_payload(ctx, agent_name, result))


def emit_agent_execution_started(
    ctx: RuntimeContext,
    *,
    run_profile: str = "smart_query",
) -> HarnessSSEEvent:
    """[阶段1] Agent 分支进入 tool 循环前的显式开始信号。"""
    return HarnessSSEEvent.create(
        **agent_execution_started_payload(
            ctx,
            run_profile=run_profile,
            action=HarnessSseAction.AGENT_STARTED,
        ),
    )


def emit_run_error(
    ctx: RuntimeContext,
    summary: str,
    *,
    error_code: str | None = None,
) -> HarnessSSEEvent:
    """[阶段2] 不可恢复失败。"""
    return HarnessSSEEvent.create(**run_error_payload(ctx, summary, error_code=error_code))


def emit_tools_available(ctx: RunContext, tool_names: list[str]) -> HarnessSSEEvent:
    """[阶段2] tools.available — agent_loop 规划阶段。"""
    return HarnessSSEEvent.create(**tools_available_payload(ctx, tool_names))
