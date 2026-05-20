# [阶段2] Explorer Agent — NL2SQL 工具链 + SQL 重试

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_runtime.context import RuntimeContext
from app.agent_runtime.events import AgentSSEEvent
from app.agent_runtime.sse_emit import emit_run_error, emit_tool_call, emit_tool_result
from app.agent_runtime.tools.build_registry import build_full_registry
from app.workflows.nodes.planner import NL2SQL_PLAN

logger = logging.getLogger(__name__)

MAX_SQL_ATTEMPTS = 3


async def run_explorer_agent(
    ctx: RuntimeContext,
    db: AsyncSession,
    state: dict[str, Any] | None = None,
    *,
    sql_retry: bool = True,
) -> AsyncIterator[AgentSSEEvent]:
    """[阶段2] 执行 Explorer 工具链；SQL 失败时最多重试 MAX_SQL_ATTEMPTS 次。"""
    registry = build_full_registry()
    if state is None:
        state = {}
    state.setdefault("query_plan", json.dumps(NL2SQL_PLAN, ensure_ascii=False))
    state.setdefault("plan_current_step", 1)
    state.setdefault(
        "semantic_model_prompt",
        ctx.semantic_model.get("prompt", ""),
    )
    state.setdefault(
        "multi_turn_context",
        "\n".join(m.content for m in ctx.memory[-6:]),
    )

    pre_sql = [
        ("search_knowledge", "Explorer"),
        ("rewrite_query", "Explorer"),
        ("inspect_schema", "Explorer"),
        ("discover_relations", "Explorer"),
    ]
    for tool_name, agent_name in pre_sql:
        tool = registry.get(tool_name)
        yield emit_tool_call(ctx, agent_name, tool_name, f"Explorer: {tool_name}")
        result = await tool._timed_run(ctx, state, db)
        yield emit_tool_result(ctx, agent_name, result)
        if result.status == "error":
            yield emit_run_error(ctx, result.summary, error_code=result.error_code)
            return

    attempts = 0
    while attempts < MAX_SQL_ATTEMPTS:
        attempts += 1
        sql_ready = True
        for tool_name in ("generate_sql", "validate_sql"):
            tool = registry.get(tool_name)
            yield emit_tool_call(
                ctx, "Explorer", tool_name, f"SQL 尝试 {attempts}/{MAX_SQL_ATTEMPTS}: {tool_name}"
            )
            result = await tool._timed_run(ctx, state, db)
            yield emit_tool_result(ctx, "Explorer", result)
            if result.status == "error":
                sql_ready = False
                break

        if not sql_ready:
            if not sql_retry or attempts >= MAX_SQL_ATTEMPTS:
                yield emit_run_error(ctx, "SQL 生成或语义校验失败", error_code="SQL_PIPELINE_FAILED")
                return
            state["sql_regenerate_reason"] = {
                "type": "validate",
                "reason": "SQL 生成或语义校验失败",
            }
            logger.info("[阶段2][Explorer] SQL 重试 %s/%s", attempts, MAX_SQL_ATTEMPTS)
            continue

        exec_tool = registry.get("execute_sql")
        yield emit_tool_call(ctx, "Explorer", "execute_sql", "执行 SQL")
        exec_result = await exec_tool._timed_run(ctx, state, db)
        yield emit_tool_result(ctx, "Explorer", exec_result)
        if exec_result.status == "ok":
            yield AgentSSEEvent.create_v2_only(
                run_id=ctx.run_id,
                event_type="agent.complete",
                agent_id=ctx.agent_id,
                thread_id=ctx.thread_id,
                agent_name="Explorer",
                status="ok",
                summary="Explorer 数据探查完成",
            )
            return
        if not sql_retry or attempts >= MAX_SQL_ATTEMPTS:
            yield emit_run_error(
                ctx,
                exec_result.summary or "SQL 执行失败",
                error_code=exec_result.error_code,
            )
            return
        state["sql_regenerate_reason"] = {
            "type": "execute",
            "reason": exec_result.summary,
        }
        logger.info("[阶段2][Explorer] SQL 执行重试 %s/%s", attempts, MAX_SQL_ATTEMPTS)

    yield emit_run_error(ctx, "Explorer 未能在重试次数内完成 SQL 链路", error_code="SQL_EXHAUSTED")
