# [阶段2] 按 mode 执行 Action 链（替代 delegate orchestrator）
# [Harness: Intelligent Routing #3 + A2A Delegation #2]
#
# mode_runner 是 execute 动作的最终分发点:
#   smart_query    → Explorer Agent (四 Tool 链: knowledge → schema → SQL ⇄ execute)
#   deep_research  → 未实现 (Phase 3+)
#   report         → 未实现 (Phase 4+)
#   其他           → UNKNOWN_MODE 错误
#
# 在调用 Agent 前先发 tools.available 事件，告知前端本模式可用的工具列表。
# 前端据此渲染执行面板的工具标签页。

from __future__ import annotations

import logging
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from app.harness.types.context import RuntimeContext
from app.harness.types.events import HarnessSSEEvent
from app.harness.agents.explorer import run_harness_explorer
from app.harness.sse.emit import emit_error
from app.harness.tools.registry import list_for_mode

logger = logging.getLogger(__name__)


async def run_mode(
    ctx: RuntimeContext,
    db: AsyncSession,
    *,
    mode: str,
) -> AsyncIterator[HarnessSSEEvent]:
    """[阶段2] execute 路径 mode 分发。"""
    tool_names = list_for_mode(mode)
    if tool_names:
        yield HarnessSSEEvent.create_v2_only(
            run_id=ctx.run_id,
            event_type="tools.available",
            agent_id=ctx.agent_id,
            thread_id=ctx.thread_id,
            status="ok",
            summary=f"可用工具: {', '.join(tool_names)}",
            text=",".join(tool_names),
        )

    if mode == "smart_query":
        async for ev in run_harness_explorer(ctx, db):
            yield ev
        return

    # TODO(Phase 3+): deep_research / report 模式未实现，当前返回 UNIMPLEMENTED 错误。
    # 答：符合 OpenSpec Phase 3/4 排期。M2 仅交付 smart_query（Explorer 四 Tool）。
    #   deep_research 需 Insight Agent；report 需 Reporter + 产物持久化，勿在 M2 硬凑。
    if mode in ("deep_research", "report"):
        yield emit_error(
            ctx,
            agent_id=ctx.agent_id,
            thread_id=ctx.thread_id,
            run_id=ctx.run_id,
            code="MODE_NOT_IMPLEMENTED",
            summary=f"模式 {mode} 将在后续里程碑实现，请暂时使用 smart_query",
        )
        return

    yield emit_error(
        ctx,
        agent_id=ctx.agent_id,
        thread_id=ctx.thread_id,
        run_id=ctx.run_id,
        code="UNKNOWN_MODE",
        summary=f"未知执行模式: {mode}",
    )
