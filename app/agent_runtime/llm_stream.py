# [阶段5] LLM chat_stream → SSE text.delta 桥接

from __future__ import annotations

from collections.abc import AsyncIterator

from app.agent_runtime.context import RuntimeContext
from app.agent_runtime.events import AgentSSEEvent
from app.agent_runtime.sse_emit import emit_text_delta
from app.core.llm import llm_service


async def stream_llm_text_deltas(
    ctx: RuntimeContext,
    system_prompt: str,
    user_prompt: str,
    *,
    agent_name: str,
    text_type: str = "TEXT",
    action: str = "llm_stream",
    temperature: float | None = None,
) -> AsyncIterator[AgentSSEEvent]:
    """[阶段5] 将 llm_service.chat_stream 转为 text.delta SSE 事件。"""
    async for delta in llm_service.chat_stream(
        system_prompt,
        user_prompt,
        temperature=temperature,
    ):
        if delta:
            yield emit_text_delta(
                ctx,
                agent_name,
                delta,
                text_type=text_type,
                action=action,
            )


async def collect_llm_stream(
    ctx: RuntimeContext,
    system_prompt: str,
    user_prompt: str,
    *,
    agent_name: str,
    text_type: str = "TEXT",
    action: str = "llm_stream",
    temperature: float | None = None,
) -> tuple[str, list[AgentSSEEvent]]:
    """[阶段5] 流式生成并收集全文（供落库 / 后续 HTML 生成）。"""
    events: list[AgentSSEEvent] = []
    parts: list[str] = []
    async for ev in stream_llm_text_deltas(
        ctx,
        system_prompt,
        user_prompt,
        agent_name=agent_name,
        text_type=text_type,
        action=action,
        temperature=temperature,
    ):
        events.append(ev)
        if ev.text:
            parts.append(ev.text)
    return "".join(parts), events
