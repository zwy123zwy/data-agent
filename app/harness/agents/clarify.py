# [阶段1] 澄清路径：引导用户补充信息（system 走 PromptLoader）

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.llm import llm_service
from app.harness.prompts import HarnessPromptKey, get_system_prompt
from app.harness.sse.emit import emit_text_delta
from app.harness.types.context import RuntimeContext
from app.harness.types.events import HarnessSSEEvent


async def stream_clarification(
    ctx: RuntimeContext,
    reason: str,
    *,
    db: AsyncSession | None = None,
) -> AsyncIterator[HarnessSSEEvent]:
    """[阶段1] 澄清文案流式输出。"""
    system_prompt = await get_system_prompt(
        HarnessPromptKey.CLARIFY,
        db=db,
        agent_id=ctx.agent_id,
        overrides=ctx.prompt_overrides,
    )
    yield HarnessSSEEvent.create_v2_only(
        run_id=ctx.run_id,
        event_type="clarification.requested",
        agent_id=ctx.agent_id,
        thread_id=ctx.thread_id,
        status="running",
        summary=f"需要澄清: {reason[:120]}",
        text=reason,
    )

    prompt = f"用户输入：{ctx.user_query}\n\n需澄清依据：{reason}\n\n请生成澄清引导语。"
    parts: list[str] = []
    async for delta in llm_service.chat_stream(system_prompt, prompt):
        if delta:
            parts.append(delta)
            yield emit_text_delta(ctx, delta, agent_name="Harness", action="clarification")

    text = "".join(parts).strip() or reason
    yield HarnessSSEEvent.create_v2_only(
        run_id=ctx.run_id,
        event_type="agent.complete",
        agent_id=ctx.agent_id,
        thread_id=ctx.thread_id,
        agent_name="Harness",
        status="ok",
        summary=text[:200],
        text=text,
    )
