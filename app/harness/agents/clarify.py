# [阶段1] 澄清路径：引导用户补充信息
# [Harness: Intelligent Routing #3] 当 LLM 无法确定用户意图时，反问用户补充信息。
#
# 澄清触发条件 (routing.py):
#   ① 0.3 ≤ confidence < 0.7: LLM 不确定意图
#   ② 数据需求但无激活数据源: smart_query/deep_research/report + has_datasource=False
#   ③ file_analysis 但无文件: file_analysis + has_files=False
#
# SSE 事件序列:
#   ① clarification.requested (思考区，展示原因)
#   ② text.delta × N (正文区流式输出澄清文案)
#   ③ agent.complete (结束标记)

from __future__ import annotations

from collections.abc import AsyncIterator

from app.harness.types.context import RuntimeContext
from app.harness.types.events import HarnessSSEEvent
from app.core.llm import llm_service
from app.harness.sse.emit import emit_text_delta

_CLARIFY_SYSTEM = """[阶段1] 用户问题不够明确，请用简短中文引导补充指标、时间范围或表名。不要编造数据。"""


async def stream_clarification(
    ctx: RuntimeContext,
    reason: str,
) -> AsyncIterator[HarnessSSEEvent]:
    """[阶段1] 澄清文案流式输出。"""
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
    async for delta in llm_service.chat_stream(_CLARIFY_SYSTEM, prompt):
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
