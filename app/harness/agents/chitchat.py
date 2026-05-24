# [阶段1] 闲聊路径：LLM 流式 text.delta
# [Harness: Intelligent Routing #3] chitchat 模式处理，最简单的执行分支。
#
# 与 Explorer 的区别:
# - 不经过 Tool 链，直接 LLM 对话
# - 流式输出 text.delta（逐 token），用户感知为打字机效果
# - 结束发送 agent.complete（非 run.complete，因为 coordinator 还会继续发 run.complete）
#
# TODO(H2): 当前 prompt 仅为 f"当前问题: {ctx.user_query}"，无历史上下文。
#   H2 恢复后注入 ctx.memory 使闲聊具备多轮感知能力。

from __future__ import annotations

from collections.abc import AsyncIterator

from app.harness.types.context import RuntimeContext
from app.harness.types.events import HarnessSSEEvent
from app.core.llm import llm_service
from app.harness.sse.emit import emit_text_delta

_CHITCHAT_SYSTEM = """[阶段1] 你是友好的数据分析助手，用简洁中文回复。不涉及编造查询结果。"""


async def stream_chitchat(ctx: RuntimeContext) -> AsyncIterator[HarnessSSEEvent]:
    """[阶段1] 闲聊模式流式输出。"""
    # TODO(H2): 无多轮上下文，连续闲聊无法感知之前的对话。H2 后应从 ctx.memory 注入历史。
    # 答：对。UI 聊天气泡在 chat_message，但 Harness 不读。H2 用 memory_context_prefix(ctx.memory)
    #   拼在 prompt 前；或依赖前端已写入的 DB + ConversationMemory.prepare。
    prompt = f"当前问题: {ctx.user_query}"

    parts: list[str] = []
    async for delta in llm_service.chat_stream(_CHITCHAT_SYSTEM, prompt):
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
