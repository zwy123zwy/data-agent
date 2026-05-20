# [阶段4] deep_research 骨架 — 多轮子任务 + Explorer 循环

from __future__ import annotations

import logging
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_runtime.agents.explorer_agent import run_explorer_agent
from app.agent_runtime.context import RuntimeContext
from app.agent_runtime.events import AgentSSEEvent

logger = logging.getLogger(__name__)

MAX_DEEP_ROUNDS = 3


async def run_deep_research(
    ctx: RuntimeContext,
    db: AsyncSession,
) -> AsyncIterator[AgentSSEEvent]:
    """[阶段4] 深度研究：最多 MAX_DEEP_ROUNDS 轮 Explorer 探查（后续可拆子任务列表）。"""
    yield AgentSSEEvent.create_v2_only(
        run_id=ctx.run_id,
        event_type="agent.think",
        agent_id=ctx.agent_id,
        thread_id=ctx.thread_id,
        status="running",
        summary=f"[阶段4] 启动深度研究（最多 {MAX_DEEP_ROUNDS} 轮）",
    )

    state: dict = {}
    for round_idx in range(1, MAX_DEEP_ROUNDS + 1):
        yield AgentSSEEvent.create_v2_only(
            run_id=ctx.run_id,
            event_type="agent.think",
            agent_id=ctx.agent_id,
            thread_id=ctx.thread_id,
            status="running",
            summary=f"深度研究第 {round_idx}/{MAX_DEEP_ROUNDS} 轮",
        )
        async for event in run_explorer_agent(ctx, db, state, sql_retry=True):
            yield event
            if event.event_type == "error":
                return

    yield AgentSSEEvent.create_v2_only(
        run_id=ctx.run_id,
        event_type="agent.complete",
        agent_id=ctx.agent_id,
        thread_id=ctx.thread_id,
        agent_name="Explorer",
        status="ok",
        summary="深度研究轮次完成",
    )
