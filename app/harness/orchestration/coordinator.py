# [阶段4] HarnessCoordinator：preflight → hydrate → Agent 执行（无 Gateway / 无 mode 分流）
#
# 数据流：
#   PreflightSnapshot → RuntimeContext → clarify? | agent_loop

from __future__ import annotations

import logging
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from app.harness.agents.clarify import stream_clarification
from app.harness.context.builder import build_runtime_context
from app.harness.orchestration.agent_loop import run_agent_loop
from app.harness.perception.preflight import run_preflight
from app.harness.planning.routing import needs_clarification_from_preflight
from app.harness.sse.actions import HarnessSseAction
from app.harness.sse.emit import (
    emit_agent_execution_started,
    emit_error,
    emit_think,
)
from app.harness.types.events import HarnessSSEEvent
from app.services.multi_turn import get_multi_turn_manager
from app.services.thread_memory import ensure_multi_turn_hydrated, resolve_stream_thread_id

logger = logging.getLogger(__name__)

_RUN_PROFILE = "smart_query"


def _fetch_conversation_history(thread_id: str) -> list[dict[str, str]]:
    """[阶段1] 多轮历史，供 Context 装配。"""
    return get_multi_turn_manager().get_messages_for_llm(thread_id)


class HarnessCoordinator:
    """[阶段4] V2 流式 Run：统一走 Agent 执行链。"""

    async def stream_run(
        self,
        *,
        agent_id: int,
        user_query: str,
        db: AsyncSession,
        thread_id: str | None,
        run_id: str,
    ) -> AsyncIterator[HarnessSSEEvent]:
        """[阶段3] preflight → hydrate → 澄清? → agent_loop。"""
        thread_id = resolve_stream_thread_id(thread_id)

        await ensure_multi_turn_hydrated(db, thread_id)
        conversation_history = _fetch_conversation_history(thread_id)

        preflight = await run_preflight(db, agent_id=agent_id, user_query=user_query)
        if preflight.blocked:
            yield emit_error(
                None,
                agent_id=agent_id,
                thread_id=thread_id,
                run_id=run_id,
                code=preflight.block_code or "PREFLIGHT_BLOCKED",
                summary="请求未通过安全校验",
            )
            return

        needs_clarify, clarify_reason = needs_clarification_from_preflight(preflight)

        ctx = await build_runtime_context(
            db,
            agent_id=agent_id,
            user_query=user_query,
            thread_id=thread_id,
            mode="smart_query",  # type: ignore[arg-type]
            run_id=run_id,
            preflight=preflight,
            conversation_history=conversation_history,
        )

        yield emit_think(
            ctx,
            summary="准备执行 Agent",
            text="进入 Agent 执行链",
            action=HarnessSseAction.THINK_DEFAULT,
        )

        if needs_clarify:
            yield emit_think(
                ctx,
                summary="需要澄清",
                text=clarify_reason or "",
                action=HarnessSseAction.CLARIFICATION,
            )
            clarify_ctx = await build_runtime_context(
                db,
                agent_id=agent_id,
                user_query=user_query,
                thread_id=thread_id,
                mode="clarification",
                run_id=run_id,
                preflight=preflight,
                conversation_history=conversation_history,
            )
            reason = clarify_reason or "请补充更多信息"
            async for ev in stream_clarification(clarify_ctx, reason, db=db):
                yield ev
            return

        yield emit_agent_execution_started(ctx, run_profile=_RUN_PROFILE)
        async for ev in run_agent_loop(ctx, db):
            yield ev
