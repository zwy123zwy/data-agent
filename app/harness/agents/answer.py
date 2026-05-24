# [阶段2] 问数回答智能体：将 sql_result 转为自然语言（M2.5 T-03）

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from app.core.llm import llm_service
from app.harness.sse.emit import emit_text_delta
from app.harness.types.context import RuntimeContext
from app.harness.types.events import HarnessSSEEvent

logger = logging.getLogger(__name__)

_ANSWER_SYSTEM = """[阶段2] 你是数据分析助手。根据用户问题与查询结果，用简洁中文给出结论与关键数字。
不要编造未出现在结果中的数据；若结果为空，说明未查到数据并建议用户改问法。"""

# [阶段2] 注入 LLM 的结果集最大字符，避免撑爆上下文
_MAX_RESULT_JSON_CHARS = 12_000


def _format_sql_result_for_prompt(sql_result: list[Any]) -> str:
    """[阶段2] 将 sql_result 序列化为 prompt 片段。"""
    if not sql_result:
        return "（查询结果为空）"
    try:
        text = json.dumps(sql_result, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        text = str(sql_result)
    if len(text) > _MAX_RESULT_JSON_CHARS:
        return text[:_MAX_RESULT_JSON_CHARS] + "\n…（结果已截断）"
    return text


async def stream_answer_from_sql(
    ctx: RuntimeContext,
    state: dict[str, Any],
) -> AsyncIterator[HarnessSSEEvent]:
    """[阶段2] 基于 state 中的 sql_result 流式输出 text.delta，最后 agent.complete。"""
    sql_result = state.get("sql_result") or []
    knowledge = (state.get("recalled_knowledge") or "").strip() or "无"
    row_count = len(sql_result) if isinstance(sql_result, list) else 0

    prompt = (
        f"用户问题: {ctx.user_query}\n\n"
        f"业务知识摘要:\n{knowledge[:2000]}\n\n"
        f"查询返回约 {row_count} 行，数据如下:\n"
        f"{_format_sql_result_for_prompt(sql_result if isinstance(sql_result, list) else [])}\n\n"
        "请用自然语言回答用户问题。"
    )

    parts: list[str] = []
    try:
        async for delta in llm_service.chat_stream(_ANSWER_SYSTEM, prompt, temperature=0.2):
            if delta:
                parts.append(delta)
                yield emit_text_delta(
                    ctx,
                    delta,
                    agent_name="Explorer",
                    action="harness.answer",
                )
    except Exception as exc:
        logger.error("[阶段2][Answer] LLM 失败: %s", exc)
        fallback = f"查询完成，共 {row_count} 行。请在下方表格查看明细。"
        yield emit_text_delta(ctx, fallback, agent_name="Explorer", action="harness.answer")
        parts.append(fallback)

    text = "".join(parts).strip() or f"查询完成，共 {row_count} 行。"
    yield HarnessSSEEvent.create_v2_only(
        run_id=ctx.run_id,
        event_type="agent.complete",
        agent_id=ctx.agent_id,
        thread_id=ctx.thread_id,
        agent_name="Explorer",
        status="ok",
        summary=text[:200],
        text=text,
    )
