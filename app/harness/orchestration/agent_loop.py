# [阶段4] Agent 循环 — ToolPicker + ExplorerState + ConstraintRunner（M4.1）

from __future__ import annotations

import logging
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.harness.agents.answer import stream_answer_from_sql
from app.harness.agents.explorer_policy import (
    apply_preflight_degrade,
    is_fatal_tool_error,
)
from app.harness.constraints.runner import ConstraintRunner
from app.harness.orchestration.tool_picker import PickDecision, build_tool_picker
from app.harness.sse.emit import (
    emit_run_error,
    emit_tool_call,
    emit_tool_result,
    emit_tools_available as emit_tools_available_sse,
)
from app.harness.tools.base import ToolResult
from app.harness.tools.registry import ToolRegistry, build_harness_registry
from app.harness.types.context import RuntimeContext
from app.harness.types.events import HarnessSSEEvent
from app.harness.types.explorer_state import ExplorerState
from app.harness.types.observation import Observation

logger = logging.getLogger(__name__)

_AGENT_LABEL = "AgentLoop"


def _max_agent_steps() -> int:
    return max(4, int(getattr(settings, "harness_agent_max_steps", 16)))


async def _run_tool(
    *,
    ctx: RuntimeContext,
    db: AsyncSession,
    registry: ToolRegistry,
    constraints: ConstraintRunner,
    tool_name: str,
    tool_state: dict,
    observations: list[Observation],
    step_index: int,
) -> ToolResult:
    """[阶段4] 单步工具执行。"""
    block = constraints.run_before(tool_name, ctx, step_index=step_index)
    if block is not None:
        blocked = ToolResult(
            status="error",
            tool_name=tool_name,
            summary=block.summary,
            error_code=block.code,
            error_severity="fatal",
        )
        observations.append(blocked.to_observation())
        return blocked

    tool = registry.get(tool_name)
    result = await tool.timed_run(ctx, tool_state, db)
    result = constraints.run_after(tool_name, ctx, result)
    observations.append(result.to_observation())
    return result


def _handle_tool_error(
    ctx: RuntimeContext,
    tool_name: str,
    result: ToolResult,
    tool_state: dict,
) -> HarnessSSEEvent | None:
    """[阶段4] 处理 Tool 错误；返回 SSE 错误事件表示应终止 Run。"""
    if not is_fatal_tool_error(result):
        if apply_preflight_degrade(tool_name, tool_state):
            return None
    return emit_run_error(
        ctx,
        result.summary or f"{tool_name} 失败",
        error_code=result.error_code,
    )


async def run_agent_loop(
    ctx: RuntimeContext,
    db: AsyncSession,
    *,
    announce_tools: bool = True,
) -> AsyncIterator[HarnessSSEEvent]:
    """[阶段4] 主循环：ToolPicker 选步 → 执行 → Observation → Answer。"""
    if announce_tools:
        registry = build_harness_registry()
        names = [d.name for d in registry.list_descriptors(ctx)]
        yield emit_tools_available_sse(ctx, names)

    registry = build_harness_registry()
    constraints = ConstraintRunner()
    picker = build_tool_picker()
    explorer = ExplorerState.from_context(ctx)
    observations: list[Observation] = []
    max_steps = _max_agent_steps()

    for step in range(max_steps):
        decision: PickDecision = await picker.pick(
            ctx=ctx,
            observations=observations,
            state=explorer,
            registry=registry,
        )

        if decision.kind == "finish":
            if explorer.has_sql_result():
                async for ev in stream_answer_from_sql(ctx, explorer.as_tool_state()):
                    yield ev
                return
            yield emit_run_error(
                ctx,
                "Agent 结束但无查询结果",
                error_code="NO_SQL_RESULT",
            )
            return

        tool_name = decision.tool_name
        if not tool_name:
            yield emit_run_error(ctx, "选步未指定工具", error_code="PICKER_EMPTY")
            return

        summary = decision.reasoning or f"{_AGENT_LABEL}: {tool_name}"
        yield emit_tool_call(ctx, _AGENT_LABEL, tool_name, summary)

        tool_state = explorer.as_tool_state()
        result = await _run_tool(
            ctx=ctx,
            db=db,
            registry=registry,
            constraints=constraints,
            tool_name=tool_name,
            tool_state=tool_state,
            observations=observations,
            step_index=step,
        )
        explorer = ExplorerState.from_tool_state(tool_state)
        yield emit_tool_result(ctx, _AGENT_LABEL, result)

        if result.status == "error":
            fatal_ev = _handle_tool_error(ctx, tool_name, result, tool_state)
            if fatal_ev is not None:
                yield fatal_ev
                return
            explorer = ExplorerState.from_tool_state(tool_state)
            continue

        if tool_name == "execute_sql" and result.status == "ok":
            async for ev in stream_answer_from_sql(ctx, explorer.as_tool_state()):
                yield ev
            return

    yield emit_run_error(
        ctx,
        f"Agent 步数已达上限（{max_steps}）",
        error_code="AGENT_MAX_STEPS",
    )
