# [阶段2] 装配 RuntimeContext（信任 Preflight；多轮 memory 暂不实现）
# TODO(H2): memory 字段恒为 []，H2 多轮记忆实施时需要 ConversationMemory.for_agent()
# TODO(H2): 需要区分 Gateway 轻量上下文 vs Agent 推理上下文（见 ISSUES-AND-REMEDIATION.md H2）

from __future__ import annotations

import logging
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.harness.types.context import HarnessMode, Permissions, RuntimeContext
from app.harness.types.preflight import PreflightSnapshot

logger = logging.getLogger(__name__)

_EXECUTE_MODES = frozenset({"smart_query", "deep_research", "report", "file_analysis"})


async def build_runtime_context(
    db: AsyncSession,
    *,
    agent_id: int,
    user_query: str,
    thread_id: str,
    mode: HarnessMode = "smart_query",
    run_id: str | None = None,
    preflight: PreflightSnapshot | None = None,
) -> RuntimeContext:
    """[阶段2] Run 开始前一次性装配；须先通过 preflight（agent_ok）。"""
    if preflight and not preflight.agent_ok:
        raise ValueError(f"Agent 不存在: {agent_id}")

    datasets = []
    semantic_model: dict = {}
    if mode in _EXECUTE_MODES and preflight and preflight.probe:
        probe = preflight.probe
        datasets = list(probe.datasets)
        if probe.semantic_prompt:
            semantic_model = {"prompt": probe.semantic_prompt}

    permissions = Permissions(
        allow_write_operations=False,
        allow_python_execution=True,
        max_sql_result_rows=10000,
    )

    ctx = RuntimeContext(
        run_id=run_id or str(uuid4()),
        thread_id=thread_id,
        agent_id=agent_id,
        user_query=user_query,
        mode=mode,
        datasets=datasets,
        semantic_model=semantic_model,
        business_knowledge=[],
        permissions=permissions,
        memory=[],
    )
    logger.info(
        "[阶段2][HarnessContext] run_id=%s datasets=%d mode=%s",
        ctx.run_id,
        len(datasets),
        mode,
    )
    return ctx
