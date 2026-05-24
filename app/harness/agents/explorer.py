# [阶段2] Explorer Agent — 四 Tool 固定管道（M2.5：severity + Answer）
# [Harness: Tool Access #1 + A2A Delegation #2]
#
# 流水线: search_knowledge → inspect_schema → [generate_sql ⇄ execute_sql]×N → stream_answer
# M2.5: 读 error_severity；知识检索可降级；SQL 重试仅由本模块 _max_sql_attempts 控制

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.harness.agents.answer import stream_answer_from_sql
from app.harness.agents.explorer_policy import (
    apply_preflight_degrade,
    is_fatal_tool_error,
)
from app.harness.sse.emit import emit_run_error, emit_tool_call, emit_tool_result
from app.harness.tools.registry import build_harness_registry
from app.harness.types.context import RuntimeContext
from app.harness.types.events import HarnessSSEEvent

logger = logging.getLogger(__name__)

_TOOL_SEQUENCE: list[tuple[str, str]] = [
    ("search_knowledge", "Explorer"),
    ("inspect_schema", "Explorer"),
]


def _max_sql_attempts() -> int:
    """[阶段2] SQL 生成/执行循环上限（单一真相源，对齐 M2.5 T-02）。"""
    return max(1, int(getattr(settings, "harness_max_sql_attempts", 3)))


async def run_harness_explorer(
    ctx: RuntimeContext,
    db: AsyncSession,
) -> AsyncIterator[HarnessSSEEvent]:
    """[阶段2] smart_query：知识 → Schema → SQL 重试环 → 自然语言回答。"""
    registry = build_harness_registry()
    state: dict[str, Any] = {}
    state.setdefault("semantic_model_prompt", ctx.semantic_model.get("prompt", ""))
    # TODO(H2): multi_turn_context 从 ctx.memory 注入
    state.setdefault("multi_turn_context", "")

    max_attempts = _max_sql_attempts()

    # ① 前置工具链（各执行一次）
    for tool_name, agent_name in _TOOL_SEQUENCE:
        tool = registry.get(tool_name)
        yield emit_tool_call(ctx, agent_name, tool_name, f"Explorer: {tool_name}")
        result = await tool.timed_run(ctx, state, db)
        yield emit_tool_result(ctx, agent_name, result)
        if result.status == "error":
            if is_fatal_tool_error(result):
                yield emit_run_error(
                    ctx,
                    result.summary,
                    error_code=result.error_code,
                )
                return
            if apply_preflight_degrade(tool_name, state):
                continue
            yield emit_run_error(
                ctx,
                result.summary or f"{tool_name} 失败",
                error_code=result.error_code,
            )
            return

    # ② SQL 生成 / 执行重试环
    attempts = 0
    while attempts < max_attempts:
        attempts += 1

        gen = registry.get("generate_sql")
        yield emit_tool_call(
            ctx,
            "Explorer",
            "generate_sql",
            f"生成 SQL ({attempts}/{max_attempts})",
        )
        gen_result = await gen.timed_run(ctx, state, db)
        yield emit_tool_result(ctx, "Explorer", gen_result)
        if gen_result.status == "error":
            if is_fatal_tool_error(gen_result) or attempts >= max_attempts:
                yield emit_run_error(
                    ctx,
                    gen_result.summary,
                    error_code=gen_result.error_code,
                )
                return
            continue

        exe = registry.get("execute_sql")
        yield emit_tool_call(ctx, "Explorer", "execute_sql", "执行 SQL")
        exe_result = await exe.timed_run(ctx, state, db)
        yield emit_tool_result(ctx, "Explorer", exe_result)

        if exe_result.status == "ok":
            async for ev in stream_answer_from_sql(ctx, state):
                yield ev
            return

        if is_fatal_tool_error(exe_result) or attempts >= max_attempts:
            yield emit_run_error(
                ctx,
                exe_result.summary or "SQL 执行失败",
                error_code=exe_result.error_code,
            )
            return
        logger.info(
            "[阶段2][Explorer] SQL 执行可重试失败，进入下一轮 %s/%s",
            attempts,
            max_attempts,
        )

    yield emit_run_error(ctx, "Explorer SQL 链路未成功", error_code="SQL_EXHAUSTED")
