# [阶段1] smart_query 最小 Runner — 线性 3 Tool（阶段3 后由 Orchestrator 替代主路径）

from __future__ import annotations

import logging
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_runtime.context import RuntimeContext
from app.agent_runtime.events import AgentSSEEvent
from app.agent_runtime.sse_emit import emit_tool_call, emit_tool_result
from app.agent_runtime.tools.registry import build_phase1_registry

logger = logging.getLogger(__name__)

PHASE1_TOOL_SEQUENCE: list[tuple[str, str]] = [
    ("search_knowledge", "Explorer"),
    ("generate_sql", "Explorer"),
    ("execute_sql", "Explorer"),
]


async def run_smart_query_minimal(
    ctx: RuntimeContext,
    db: AsyncSession,
) -> AsyncIterator[AgentSSEEvent]:
    """[阶段1] 顺序执行 3 Tool；Gateway fallback 或未知 mode 时使用。"""
    registry = build_phase1_registry()
    workflow_state: dict = {}

    yield AgentSSEEvent.create_v2_only(
        run_id=ctx.run_id,
        event_type="agent.think",
        agent_id=ctx.agent_id,
        thread_id=ctx.thread_id,
        status="ok",
        summary="[阶段1] 最小 smart_query 工具链",
    )

    for tool_name, agent_name in PHASE1_TOOL_SEQUENCE:
        tool = registry.get(tool_name)
        yield emit_tool_call(ctx, agent_name, tool_name, f"正在执行 {tool_name}…")
        result = await tool._timed_run(ctx, workflow_state, db)
        yield emit_tool_result(ctx, agent_name, result)
        if result.status == "error":
            yield AgentSSEEvent.create_v2_only(
                run_id=ctx.run_id,
                event_type="error",
                agent_id=ctx.agent_id,
                thread_id=ctx.thread_id,
                status="error",
                summary=result.summary,
                error=result.error_code or result.summary,
            )
            return

    yield AgentSSEEvent.create_v2_only(
        run_id=ctx.run_id,
        event_type="agent.complete",
        agent_id=ctx.agent_id,
        thread_id=ctx.thread_id,
        agent_name="Explorer",
        status="ok",
        summary="最小闭环完成",
    )
