# [阶段2·兼容] Explorer 入口 — M4.2 已收拢至 agent_loop

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from app.harness.orchestration.agent_loop import run_agent_loop
from app.harness.types.context import RuntimeContext
from app.harness.types.events import HarnessSSEEvent


async def run_harness_explorer(
    ctx: RuntimeContext,
    db: AsyncSession,
) -> AsyncIterator[HarnessSSEEvent]:
    """[阶段4] 兼容别名：等同 run_agent_loop（不重复发 tools.available）。"""
    async for ev in run_agent_loop(ctx, db, announce_tools=False):
        yield ev
