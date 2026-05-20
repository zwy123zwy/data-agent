# [阶段3] Insight Agent — Python 分析链（可跳过）

from __future__ import annotations

import logging
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_runtime.context import RuntimeContext
from app.agent_runtime.events import AgentSSEEvent
from app.agent_runtime.sse_emit import emit_run_error, emit_tool_call, emit_tool_result
from app.agent_runtime.tools.build_registry import build_full_registry

logger = logging.getLogger(__name__)

INSIGHT_TOOLS = [
    ("generate_python", "Insight"),
    ("execute_python", "Insight"),
    ("analyze_result", "Insight"),
]

# [阶段3] 行数低于此阈值时跳过 Insight（Reporter 直出 SQL 结果）
SKIP_INSIGHT_MAX_ROWS = 10


def should_skip_insight(state: dict) -> bool:
    """[阶段3] 简单结果集过小则跳过 Python 分析。"""
    rows = state.get("sql_result") or []
    if isinstance(rows, list) and len(rows) <= SKIP_INSIGHT_MAX_ROWS:
        return True
    return False


async def run_insight_agent(
    ctx: RuntimeContext,
    db: AsyncSession,
    state: dict,
) -> AsyncIterator[AgentSSEEvent]:
    """[阶段3] 执行 Insight 三工具链。"""
    if should_skip_insight(state):
        yield AgentSSEEvent.create_v2_only(
            run_id=ctx.run_id,
            event_type="agent.think",
            agent_id=ctx.agent_id,
            thread_id=ctx.thread_id,
            status="ok",
            summary="[阶段3] 结果行数较少，跳过 Insight 分析",
        )
        return

    registry = build_full_registry()
    for tool_name, agent_name in INSIGHT_TOOLS:
        tool = registry.get(tool_name)
        yield emit_tool_call(ctx, agent_name, tool_name, f"Insight: {tool_name}")
        result = await tool._timed_run(ctx, state, db)
        yield emit_tool_result(ctx, agent_name, result)
        if result.status == "error":
            yield emit_run_error(ctx, result.summary, error_code=result.error_code)
            return

    yield AgentSSEEvent.create_v2_only(
        run_id=ctx.run_id,
        event_type="agent.complete",
        agent_id=ctx.agent_id,
        thread_id=ctx.thread_id,
        agent_name="Insight",
        status="ok",
        summary="Insight 分析完成",
    )
