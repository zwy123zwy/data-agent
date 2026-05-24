# [阶段2] Harness SSE 事件构造（独立于 agent_runtime.sse_emit）
# [Harness: Observability #6]
#
# 事件类型与前端展示位置:
#   agent.think  → 思考区（可折叠时间线），展示 Gateway 分类、路由决策等内部推理
#   tool.call    → 思考区，展示工具调用开始
#   tool.result  → 思考区，展示工具调用结果（含 artifact 引用）
#   text.delta   → 正文区（主对话气泡），流式逐字输出
#   error        → 错误提示，终止当前 Run
#   run.complete → Run 结束标记，前端据此更新会话状态

from __future__ import annotations

from app.harness.tools.base import ToolResult
from app.harness.types.context import RuntimeContext
from app.harness.types.events import HarnessSSEEvent


def _artifact_refs(result: ToolResult) -> list[dict]:
    return [{"id": a.id, "type": a.type} for a in result.artifacts]


def emit_think(
    ctx: RuntimeContext,
    *,
    summary: str,
    text: str = "",
    action: str = "harness.think",
) -> HarnessSSEEvent:
    """[阶段2] 思考区 agent.think。"""
    return HarnessSSEEvent.create(
        run_id=ctx.run_id,
        event_type="agent.think",
        agent_id=ctx.agent_id,
        thread_id=ctx.thread_id,
        action=action,
        status="ok",
        summary=summary[:200],
        text=text or summary,
    )


def emit_text_delta(
    ctx: RuntimeContext,
    delta: str,
    *,
    agent_name: str = "Harness",
    action: str = "harness.reply",
) -> HarnessSSEEvent:
    """[阶段2] 正文区 text.delta。"""
    return HarnessSSEEvent.create(
        run_id=ctx.run_id,
        event_type="text.delta",
        agent_id=ctx.agent_id,
        thread_id=ctx.thread_id,
        agent_name=agent_name,
        action=action,
        status="running",
        text=delta,
        text_type="TEXT",
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
    return HarnessSSEEvent.create(
        run_id=run_id,
        event_type="error",
        agent_id=agent_id,
        thread_id=thread_id,
        status="error",
        summary=summary[:200],
        error=code,
        text=summary,
    )


def emit_tool_call(
    ctx: RuntimeContext,
    agent_name: str,
    tool_name: str,
    summary: str,
) -> HarnessSSEEvent:
    """[阶段2] tool.call。"""
    return HarnessSSEEvent.create(
        run_id=ctx.run_id,
        event_type="tool.call",
        agent_id=ctx.agent_id,
        thread_id=ctx.thread_id,
        agent_name=agent_name,
        action=tool_name,
        status="running",
        summary=summary[:200],
    )


def emit_tool_result(
    ctx: RuntimeContext,
    agent_name: str,
    result: ToolResult,
) -> HarnessSSEEvent:
    """[阶段2] tool.result（含 V1 RESULT_SET 兼容字段）。"""
    return HarnessSSEEvent.create(
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


def emit_run_error(
    ctx: RuntimeContext,
    summary: str,
    *,
    error_code: str | None = None,
) -> HarnessSSEEvent:
    """[阶段2] 不可恢复失败。"""
    return HarnessSSEEvent.create(
        run_id=ctx.run_id,
        event_type="error",
        agent_id=ctx.agent_id,
        thread_id=ctx.thread_id,
        status="error",
        summary=summary[:200],
        error=error_code or summary[:200],
    )
