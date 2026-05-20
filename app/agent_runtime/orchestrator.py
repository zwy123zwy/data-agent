# [阶段3] Orchestrator — LangGraph StateGraph 编排 smart_query / report / deep_research

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Any, Literal

from langgraph.graph import END, StateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_runtime.agents.explorer_agent import run_explorer_agent
from app.agent_runtime.agents.insight_agent import run_insight_agent
from app.agent_runtime.agents.report_agent import run_report_agent
from app.agent_runtime.context import RuntimeContext
from app.agent_runtime.context_engine import ContextEngine
from app.agent_runtime.deep_research_runner import run_deep_research
from app.agent_runtime.events import AgentSSEEvent
from app.agent_runtime.llm_stream import stream_llm_text_deltas
from app.agent_runtime.run_persistence import RunPersistenceService
from app.agent_runtime.state import AgentRunState, RunMetrics
from app.agent_runtime.smart_query_runner import run_smart_query_minimal
logger = logging.getLogger(__name__)

ModeType = Literal["smart_query", "deep_research", "report", "chitchat", "clarification"]


def _max_rounds(mode: str) -> int:
    return 30 if mode == "deep_research" else 10


# [阶段5] TODO: 迁入 prompt_config service（docs/05-MODULE-BOUNDARIES-REVIEW §2.4）
CHITCHAT_SYSTEM_PROMPT = """你是一个友好的 AI 数据分析助手。
用户当前的问题不涉及数据库查询或数据分析，请用自然、简洁的语言回复。
如果用户打招呼，热情回应；如果用户问你的能力，介绍你能做数据查询和分析。
始终用中文回复。"""

# [阶段5] TODO: 迁入 prompt_config service
CLARIFY_SYSTEM_PROMPT = """你是数据分析助手。用户的问题不够明确，无法直接查询数据。
请用简短、友好的中文引导用户补充：想查什么指标/表、时间范围、是否需要报告。
不要编造查询结果，一两段即可。"""


async def stream_clarification_reply(
    ctx: RuntimeContext,
    reason: str,
) -> AsyncIterator[AgentSSEEvent]:
    """[阶段5] 澄清路径：LLM 流式 text.delta，主对话区逐字展示。"""
    prompt = (
        f"用户输入：{ctx.user_query}\n\n"
        f"系统判断需澄清，依据：{reason}\n\n"
        "请生成给用户的澄清引导语。"
    )
    parts: list[str] = []
    try:
        async for ev in stream_llm_text_deltas(
            ctx,
            CLARIFY_SYSTEM_PROMPT,
            prompt,
            agent_name="Explorer",
            text_type="TEXT",
            action="clarification",
        ):
            yield ev
            if ev.text:
                parts.append(ev.text)
        text = "".join(parts).strip() or reason
    except Exception as exc:
        logger.warning("[阶段5][Clarify] 流式失败，降级文案: %s", exc)
        text = reason or "请补充您想查询的数据范围或具体指标。"
        yield AgentSSEEvent.create_v2_only(
            run_id=ctx.run_id,
            event_type="text.delta",
            agent_id=ctx.agent_id,
            thread_id=ctx.thread_id,
            agent_name="Explorer",
            action="clarification",
            status="running",
            text=text,
            text_type="TEXT",
        )

    yield AgentSSEEvent.create_v2_only(
        run_id=ctx.run_id,
        event_type="agent.complete",
        agent_id=ctx.agent_id,
        thread_id=ctx.thread_id,
        agent_name="Explorer",
        status="ok",
        summary=text[:200],
        text_type="TEXT",
        text=text,
    )


async def _run_chitchat(ctx: RuntimeContext) -> AsyncIterator[AgentSSEEvent]:
    """[阶段5] 闲聊模式：LLM 流式 text.delta 逐字输出。"""
    multi_turn = "\n".join(m.content for m in ctx.memory[-6:])
    if multi_turn:
        prompt = f"对话历史:\n{multi_turn}\n\n当前问题: {ctx.user_query}"
    else:
        prompt = ctx.user_query

    parts: list[str] = []
    try:
        async for ev in stream_llm_text_deltas(
            ctx,
            CHITCHAT_SYSTEM_PROMPT,
            prompt,
            agent_name="Explorer",
            text_type="TEXT",
            action="chitchat",
        ):
            yield ev
            if ev.text:
                parts.append(ev.text)
        text = "".join(parts).strip() or "你好，我是数据分析助手。"
    except Exception as exc:
        logger.warning("[阶段5][Chitchat] 流式失败，降级文案: %s", exc)
        text = "抱歉，我暂时无法回复，请稍后再试。"
        yield AgentSSEEvent.create_v2_only(
            run_id=ctx.run_id,
            event_type="text.delta",
            agent_id=ctx.agent_id,
            thread_id=ctx.thread_id,
            agent_name="Explorer",
            action="chitchat",
            status="running",
            text=text,
            text_type="TEXT",
        )

    yield AgentSSEEvent.create_v2_only(
        run_id=ctx.run_id,
        event_type="agent.complete",
        agent_id=ctx.agent_id,
        thread_id=ctx.thread_id,
        agent_name="Explorer",
        status="ok",
        summary=text[:200],
        text_type="TEXT",
        text=text,
    )


async def run_orchestrated_loop(
    ctx: RuntimeContext,
    db: AsyncSession,
    mode: ModeType,
) -> AsyncIterator[AgentSSEEvent]:
    """[阶段3] 按 mode 分发；smart_query 走 Explorer→Insight→Reporter。"""
    if mode == "chitchat":
        async for e in _run_chitchat(ctx):
            yield e
        return

    if mode == "clarification":
        yield AgentSSEEvent.create_v2_only(
            run_id=ctx.run_id,
            event_type="clarification.requested",
            agent_id=ctx.agent_id,
            thread_id=ctx.thread_id,
            status="running",
            summary="需要用户补充信息后再执行",
        )
        return

    if mode == "deep_research":
        async for e in run_deep_research(ctx, db):
            yield e
        return

    if mode == "smart_query":
        # [阶段3] 完整三 Agent 路径
        workflow_state: dict[str, Any] = {}
        async for e in run_explorer_agent(ctx, db, workflow_state):
            yield e
            if e.event_type == "error":
                return
        if not workflow_state.get("sql_result"):
            yield AgentSSEEvent.create_v2_only(
                run_id=ctx.run_id,
                event_type="error",
                agent_id=ctx.agent_id,
                thread_id=ctx.thread_id,
                status="error",
                summary="Explorer 未产生查询结果",
                error="NO_SQL_RESULT",
            )
            return
        async for e in run_insight_agent(ctx, db, workflow_state):
            yield e
            if e.event_type == "error":
                return
        async for e in run_report_agent(ctx, db, workflow_state):
            yield e
            if e.event_type == "error":
                return
        return

    if mode == "report":
        workflow_state: dict[str, Any] = {}
        async for e in run_explorer_agent(ctx, db, workflow_state):
            yield e
            if e.event_type == "error":
                return
        if not workflow_state.get("sql_result") and not workflow_state.get("generated_sql"):
            yield AgentSSEEvent.create_v2_only(
                run_id=ctx.run_id,
                event_type="error",
                agent_id=ctx.agent_id,
                thread_id=ctx.thread_id,
                status="error",
                summary="Explorer 未产生可报告的数据",
                error="NO_REPORT_DATA",
            )
            return
        async for e in run_report_agent(ctx, db, workflow_state):
            yield e
        return

    # 未知 mode 降级阶段1 最小链（仍会经 run_v2_orchestrator 持久化）
    logger.warning("[Orchestrator] 未知 mode=%s，降级 run_smart_query_minimal", mode)
    async for e in run_smart_query_minimal(ctx, db):
        yield e


# ── LangGraph 骨架（状态机登记，便于阶段4 扩展 interrupt/HITL）──


def _build_orchestrator_graph():
    """[阶段3] 注册节点拓扑；实际 SSE 由 run_orchestrated_loop 驱动。"""

    async def node_start(state: AgentRunState) -> dict:
        return {"round_count": state.get("round_count", 0) + 1}

    graph = StateGraph(AgentRunState)
    graph.add_node("start", node_start)
    graph.set_entry_point("start")
    graph.add_edge("start", END)
    return graph.compile()


_compiled_graph = None


def get_orchestrator_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = _build_orchestrator_graph()
    return _compiled_graph


async def run_v2_orchestrator(
    *,
    agent_id: int,
    user_query: str,
    thread_id: str,
    run_id: str,
    db: AsyncSession,
    mode: ModeType,
) -> AsyncIterator[AgentSSEEvent]:
    """[阶段3] Controller 入口：装配 Context → 编排 → 可选持久化。"""
    try:
        ctx = await ContextEngine().build_context(
            agent_id=agent_id,
            user_query=user_query,
            thread_id=thread_id,
            db=db,
            mode=mode,
            run_id=run_id,
        )
    except ValueError as exc:
        msg = str(exc)
        yield AgentSSEEvent.create_v2_only(
            run_id=run_id,
            event_type="error",
            agent_id=agent_id,
            thread_id=thread_id,
            status="error",
            summary=msg,
            error="AGENT_NOT_FOUND" if "不存在" in msg else "CONTEXT_BUILD_FAILED",
        )
        return

    events: list[AgentSSEEvent] = []
    async for event in run_orchestrated_loop(ctx, db, mode):
        events.append(event)
        yield event

    # [阶段4] Run 结束落库
    try:
        await RunPersistenceService.persist_run(
            db,
            ctx=ctx,
            events=events,
            metrics=RunMetrics(
                total_llm_calls=0,
                total_tokens=0,
                total_duration_ms=0,
                tools_called=[],
                errors_count=sum(1 for e in events if e.event_type == "error"),
            ),
        )
    except Exception as exc:
        logger.warning("[阶段4] Run 持久化跳过: %s", exc)
