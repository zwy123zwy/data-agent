# [阶段1] 闲聊路径：LLM 流式 text.delta

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.llm import llm_service
from app.harness.prompts import HarnessPromptKey, get_system_prompt
from app.harness.sse.emit import emit_text_delta
from app.harness.types.context import Message, RuntimeContext
from app.harness.types.events import HarnessSSEEvent


def _format_memory(memory: list[Message]) -> str:
    """[阶段1] 将 ctx.memory 格式化为 prompt 前缀。"""
    if not memory:
        return ""
    lines = ["## 历史对话"]
    for msg in memory[-10:]:
        label = "用户" if msg.role == "user" else "助手"
        text = (msg.content or "").strip()[:400]
        if text:
            lines.append(f"{label}: {text}")
    lines.append("")
    return "\n".join(lines)


async def stream_chitchat(
    ctx: RuntimeContext,
    *,
    db: AsyncSession | None = None,
) -> AsyncIterator[HarnessSSEEvent]:
    """[阶段1] 闲聊模式流式输出；system 从 prompts/harness/chitchat.system.md 加载。"""
    system_prompt = await get_system_prompt(
        HarnessPromptKey.CHITCHAT,
        db=db,
        agent_id=ctx.agent_id,
        overrides=ctx.prompt_overrides,
    )
    history = _format_memory(ctx.memory)
    prompt = "\n".join(
        p for p in (history, f"## 当前问题\n{ctx.user_query}") if p
    )

    parts: list[str] = []
    async for delta in llm_service.chat_stream(system_prompt, prompt):
        if delta:
            parts.append(delta)
            yield emit_text_delta(ctx, delta, agent_name="Harness", action="chitchat")

    text = "".join(parts).strip() or "你好，我是数据分析助手。"
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
