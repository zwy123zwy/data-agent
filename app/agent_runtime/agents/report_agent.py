# [阶段3] Reporter Agent — 报告生成（Markdown 流式 + HTML 收尾）

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_runtime.context import RuntimeContext
from app.agent_runtime.events import AgentSSEEvent
from app.agent_runtime.llm_stream import stream_llm_text_deltas
from app.agent_runtime.sse_emit import emit_run_error, emit_tool_call, emit_tool_result
from app.agent_runtime.tools.base import ToolResult
from app.core.config import settings
from app.workflows.nodes.report_generator import (
    _build_analysis_steps_and_data,
    _build_user_requirements_and_plan,
    _load_report_prompt,
    _recommend_chart,
    generate_html_report,
)
from app.workflows.state import get_canonical_query

logger = logging.getLogger(__name__)


async def run_report_agent(
    ctx: RuntimeContext,
    db: AsyncSession,
    state: dict,
) -> AsyncIterator[AgentSSEEvent]:
    """[阶段3] 流式生成 Markdown 报告，再生成 HTML 并发出 tool.result。"""
    yield emit_tool_call(ctx, "Reporter", "generate_report", "正在生成分析报告…")

    user_query = get_canonical_query(state)
    agent_id = state.get("agent_id", ctx.agent_id)
    sql_memory = state.get("sql_result_list_memory") or []
    if not sql_memory and state.get("sql_result"):
        sql_memory = [{"result": state["sql_result"]}]
    python_analysis = state.get("python_analysis", "")
    python_output = state.get("python_output", "")

    plan = state.get("query_plan")
    if isinstance(plan, str):
        try:
            plan = json.loads(plan)
        except json.JSONDecodeError:
            plan = {}

    try:
        report_system_prompt = await _load_report_prompt(agent_id)
        user_requirements = _build_user_requirements_and_plan(user_query, plan)
        analysis_data = _build_analysis_steps_and_data(
            plan, sql_memory, python_analysis, python_output
        )
        summary_and_recommendations = ""
        for step in (plan.get("execution_plan") or []):
            tp = step.get("tool_parameters") or {}
            if tp.get("summary_and_recommendations"):
                summary_and_recommendations = tp["summary_and_recommendations"]
                break

        full_user_prompt = (
            f"{user_requirements}\n\n"
            f"{analysis_data}\n\n"
            f"## 报告大纲\n{summary_and_recommendations or '根据分析结果生成报告'}\n\n"
            f"请生成完整的 Markdown 分析报告。"
        )

        parts: list[str] = []
        async for ev in stream_llm_text_deltas(
            ctx,
            report_system_prompt,
            full_user_prompt,
            agent_name="Reporter",
            text_type="MARK_DOWN",
            action="generate_report",
            temperature=0.3,
        ):
            yield ev
            if ev.text:
                parts.append(ev.text)

        report_md = "".join(parts).strip()
        state["report"] = report_md
        state["markdown_report"] = report_md

        chart_configs = []
        if settings.enable_sql_result_chart and sql_memory:
            for entry in sql_memory:
                result = entry.get("result") if isinstance(entry, dict) else None
                if result:
                    cfg = await _recommend_chart(result)
                    if cfg:
                        chart_configs.append(cfg)

        html_report = generate_html_report(report_md, chart_configs, state)
        state["html_report"] = html_report

        result = ToolResult(
            status="ok",
            tool_name="generate_report",
            summary="报告生成完成",
            v1_text=html_report or report_md,
            v1_text_type="HTML" if html_report else "MARK_DOWN",
        )
        yield emit_tool_result(ctx, "Reporter", result)

    except Exception as exc:
        logger.exception("[阶段3][Reporter] 报告生成失败")
        yield emit_run_error(ctx, str(exc)[:200], error_code="REPORT_ERROR")
        return

    yield AgentSSEEvent.create_v2_only(
        run_id=ctx.run_id,
        event_type="agent.complete",
        agent_id=ctx.agent_id,
        thread_id=ctx.thread_id,
        agent_name="Reporter",
        status="ok",
        summary="Reporter 报告完成",
    )
