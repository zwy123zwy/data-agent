# [阶段1] Preflight：机械校验 Agent/数据源/注入，产出 PreflightSnapshot

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.harness.perception.datasource_probe import run_datasource_probe
from app.harness.perception.prompt_guard import scan_prompt
from app.harness.types.preflight import PreflightSnapshot
from app.services.agent_service import AgentService

logger = logging.getLogger(__name__)


def _empty_pass(agent_id: int) -> PreflightSnapshot:
    """[阶段1] 开关关闭时返回通过快照（便于灰度回滚）。"""
    return PreflightSnapshot(agent_ok=True, agent_id=agent_id)


async def run_preflight(
    db: AsyncSession,
    *,
    agent_id: int,
    user_query: str,
    nl2sql_only: bool = False,
) -> PreflightSnapshot:
    """[阶段1] 执行 ② 用户校验，不调 LLM。"""
    if not getattr(settings, "harness_v2_preflight_enabled", True):
        return _empty_pass(agent_id)

    guard = scan_prompt(user_query)
    agent = await AgentService.get_agent(db, agent_id)
    if not agent:
        return PreflightSnapshot(
            agent_ok=False,
            agent_id=agent_id,
            risk_level="block",
            blocked=True,
            block_code="AGENT_NOT_FOUND",
        )

    if guard.risk_level == "block":
        return PreflightSnapshot(
            agent_ok=True,
            agent_id=agent_id,
            risk_level="block",
            blocked=True,
            block_code=guard.code or "PROMPT_INJECTION",
        )

    # [阶段2] 一次探测，probe 供 builder 装配 datasets / semantic_model（避免重复查库）
    probe = await run_datasource_probe(db, agent_id=agent_id)

    snap = PreflightSnapshot(
        agent_ok=True,
        agent_id=agent_id,
        risk_level=guard.risk_level,
        blocked=False,
        has_datasource=probe.has_datasource,
        has_files=False,
        select_tables=list(probe.select_tables),
        semantic_warn=probe.semantic_warn,
        nl2sql_only=nl2sql_only,
        probe=probe,
    )
    logger.info(
        "[阶段1][Preflight] agent_id=%s has_ds=%s tables=%d blocked=%s",
        agent_id,
        probe.has_datasource,
        len(probe.select_tables),
        snap.blocked,
    )
    return snap
